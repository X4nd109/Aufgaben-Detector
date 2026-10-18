"""
digi4school_service.py - Automatisierter Download von digitalen Schulbüchern von Digi4School.
Erstellt durchsuchbare OCR-PDFs mit Inhaltsverzeichnis (Sidebar & Klick-Links) und synchronisierten Seitenzahlen.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor, as_completed
import io
import logging
import os
from pathlib import Path
import re
import shutil
import statistics
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image
from playwright.async_api import ElementHandle, Page, async_playwright
import pytesseract

logger = logging.getLogger("Digi4SchoolService")


def find_tesseract(custom_cmd: Optional[str] = None) -> str:
    """Sucht die tesseract.exe auf Windows oder im System-Pfad."""
    if custom_cmd and os.path.isfile(custom_cmd):
        return custom_cmd

    which_path = shutil.which("tesseract")
    if which_path:
        return which_path

    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Tesseract-OCR\tesseract.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Tesseract-OCR\tesseract.EXE"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c

    raise FileNotFoundError(
        "Tesseract OCR was not found. Please install Tesseract via:\n"
        "  winget install -e --id UB-Mannheim.TesseractOCR\n"
        "or make sure that tesseract.exe is in your PATH."
    )


def parse_page_ranges(range_str: str, max_pages: Optional[int] = None) -> List[int]:
    """Parst Seitenangaben wie '1-10', '1,3,5-8', '20-end' in eine sortierte Liste."""
    range_str = range_str.strip().lower()
    if range_str in ("all", "alle"):
        if not max_pages:
            raise ValueError("For 'all', the total number of pages must be known.")
        return list(range(1, max_pages + 1))

    pages = set()
    parts = range_str.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s.strip())
            if end_s.strip() in ("end", "all", "max"):
                if not max_pages:
                    raise ValueError(f"End page for '{part}' unknown.")
                end = max_pages
            else:
                end = int(end_s.strip())
            for p in range(start, end + 1):
                pages.add(p)
        else:
            pages.add(int(part))

    sorted_pages = sorted(list(pages))
    if max_pages:
        sorted_pages = [p for p in sorted_pages if 1 <= p <= max_pages]
    return sorted_pages


async def dismiss_popups(page: Page) -> None:
    """Entfernt Info-Touren, Modals und fängt Fehler 911 automatisch ab."""
    try:
        await page.evaluate("""() => {
            const candidates = Array.from(document.querySelectorAll('button, a, div[role="button"], span, ion-button'));
            for (const b of candidates) {
                const txt = (b.innerText || '').toLowerCase().trim();
                if (txt.includes('später') || txt.includes('vielleicht später') || txt.includes('ausschalten')) {
                    try { b.click(); } catch(e) {}
                }
            }

            const killSelectors = [
                '.cdk-overlay-backdrop', '.cdk-overlay-container',
                '.shepherd-element', '.shepherd-modal', '.shepherd-content',
                '.introjs-overlay', '.introjs-hints', '.introjs-tooltip',
                '.modal-backdrop', 'ion-backdrop', '.backdrop',
                'div[class*="tour"]', 'div[class*="shepherd"]', 'div[class*="backdrop"]'
            ];
            for (const sel of killSelectors) {
                document.querySelectorAll(sel).forEach(el => {
                    try { el.remove(); } catch(e) {}
                });
            }

            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            const toRemove = [];
            while (walker.nextNode()) {
                const val = walker.currentNode.nodeValue || '';
                if (val.includes('Info-Tour') || val.includes('Funktionen des E-Book')) {
                    let parent = walker.currentNode.parentElement;
                    while (parent && parent !== document.body && parent.tagName !== 'MAIN') {
                        if (parent.offsetWidth < 900 && parent.offsetHeight < 700) {
                            toRemove.push(parent);
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }
            }
            toRemove.forEach(el => {
                try { el.remove(); } catch(e) {}
            });

            const viewers = document.querySelectorAll('#viewer, .page, #pg1, main, [id^="pg"], canvas');
            viewers.forEach(v => {
                v.style.opacity = '1';
                v.style.filter = 'none';
            });
        }""")
    except Exception:
        pass

    try:
        err_911 = await page.query_selector('text="Fehler 911"')
        if err_911 and await err_911.is_visible():
            ok_btn = await page.query_selector('button:has-text("OK"), ion-button:has-text("OK")')
            if ok_btn:
                await ok_btn.click()
                await page.wait_for_timeout(1000)
            await page.reload(wait_until="networkidle")
            await page.wait_for_timeout(2000)
    except Exception:
        pass


async def login_to_digi4school(page: Page, email: str, password: str, timeout: int = 30) -> None:
    """Führt den Login bei digi4school.at durch."""
    await page.goto("https://digi4school.at/login", wait_until="networkidle", timeout=timeout * 1000)

    if "/login" not in page.url:
        return

    email_sel = 'input[type="email"], input[autocomplete="email"], input[name="ion-input-0"]'
    await page.wait_for_selector(email_sel, timeout=15000)
    await page.fill(email_sel, email)

    pass_sel = 'input[type="password"], input[autocomplete="current-password"], input[name="ion-input-1"]'
    await page.wait_for_selector(pass_sel, timeout=15000)
    await page.fill(pass_sel, password)

    submit_sel = 'ion-button[type="submit"], button[type="submit"], ion-button:has-text("Anmelden")'
    submit_btn = await page.query_selector(submit_sel)
    if submit_btn:
        await submit_btn.click()
    else:
        await page.press(pass_sel, "Enter")

    start_time = time.time()
    logged_in = False
    while time.time() - start_time < timeout:
        await asyncio.sleep(1)
        curr_url = page.url
        if "/login" not in curr_url:
            logged_in = True
            break

        error_elem = await page.query_selector('.alert-message, .error-message, ion-toast, [role="alert"]')
        if error_elem:
            err_text = (await error_elem.inner_text()).strip()
            if err_text:
                raise RuntimeError(f"Digi4School login failed: {err_text}")

    if not logged_in:
        body_text = await page.inner_text("body")
        if "falsch" in body_text.lower() or "ungültig" in body_text.lower():
            raise RuntimeError("Digi4School login failed: Invalid email or wrong password.")
        raise TimeoutError(f"Digi4School login timeout after {timeout}s.")


async def fetch_user_books(page: Page) -> List[dict]:
    """Lädt das Bücherregal des Kontos."""
    try:
        data = await page.evaluate("""async () => {
            try {
                const res = await fetch('/br/xhr/v2/synch');
                if (res.ok) return await res.json();
            } catch(e) {}
            return null;
        }""")
        if data and isinstance(data, dict):
            books = data.get("books", [])
            if books:
                return books
    except Exception:
        pass

    try:
        api_res = await page.request.get("https://digi4school.at/br/xhr/v2/synch")
        if api_res.ok:
            data = await api_res.json()
            books = data.get("books", [])
            if books:
                return books
    except Exception:
        pass

    if "/login" in page.url:
        await page.goto("https://digi4school.at/", wait_until="networkidle", timeout=15000)

    books = await page.evaluate(r"""() => {
        const results = [];
        const items = document.querySelectorAll('a[data-code], ion-item[data-code], [data-code]');
        items.forEach(el => {
            const code = el.getAttribute('data-code');
            const title = (el.innerText || '').split('\n')[0].trim();
            if (code && title) {
                results.push({ code, title });
            }
        });
        return results;
    }""")
    return books or []


async def open_book_and_resolve_viewer(context, page: Page, book_item: dict, timeout: int = 45) -> Tuple[Page, str]:
    """Öffnet das Buch und folgt Weiterleitungen bis zum tatsächlichen Viewer."""
    code = book_item.get("code")
    book_id = book_item.get("id")
    title = book_item.get("title", code)

    opened_pages: List[Page] = []
    def on_page_opened(new_p: Page):
        opened_pages.append(new_p)
    context.on("page", on_page_opened)

    if "digi4school.at" not in page.url or "/login" in page.url or "/br/xhr" in page.url:
        await page.goto("https://digi4school.at/", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1500)

    title_words = [w for w in re.sub(r'[^\w\s]', '', title).split() if len(w) > 3][:3]
    title_snippet = " ".join(title_words)

    clicked = False
    try:
        clicked = await page.evaluate("""({ code, bookId, snippet }) => {
            const candidates = Array.from(document.querySelectorAll('ion-item, ion-card, div, a, tr, li'));
            for (const el of candidates) {
                const text = (el.innerText || '').toLowerCase();
                const hasCode = code && (el.getAttribute('data-code') === code || text.includes(code.toLowerCase()));
                const hasId = bookId && (el.getAttribute('data-id') === String(bookId) || (el.getAttribute('href') || '').includes(String(bookId)));
                const hasSnippet = snippet && text.includes(snippet.toLowerCase());

                if (hasCode || hasId || hasSnippet) {
                    const clickTarget = el.querySelector('a, button, img, ion-button') || el;
                    clickTarget.click();
                    return true;
                }
            }
            return false;
        }""", {"code": code, "bookId": book_id, "snippet": title_snippet})
    except Exception:
        pass

    if not clicked:
        nav_candidates = []
        if book_id:
            nav_candidates.append(f"https://digi4school.at/br/find/{book_id}/")
            nav_candidates.append(f"https://digi4school.at/ebook/{book_id}")
        if code:
            nav_candidates.append(f"https://digi4school.at/ebook/{code}")

        for target_nav_url in nav_candidates:
            try:
                await page.goto(target_nav_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                if any(dom in page.url for dom in ["hpthek.at", "a.digi4school.at", "trauner.at", "oebv.at"]):
                    break
            except Exception:
                pass

    start_t = time.time()
    active_page = page
    final_url = active_page.url

    while time.time() - start_t < timeout:
        await asyncio.sleep(1.0)
        if opened_pages:
            active_page = opened_pages[-1]

        try:
            await active_page.evaluate("""() => {
                const f = document.querySelector('form');
                if (f) {
                    const action = (f.action || '').toLowerCase();
                    if (action.includes('hpthek') || action.includes('lti') || action.includes('ebook') || action.includes('launch') || action.includes('token')) {
                        const btn = f.querySelector('button, input[type="submit"]');
                        if (btn) {
                            btn.click();
                        } else {
                            HTMLFormElement.prototype.submit.call(f);
                        }
                    }
                }
                const link = document.querySelector('a[href*="hpthek"], a[href*="ebook"]');
                if (link && (link.innerText || '').toLowerCase().includes('weiter')) {
                    link.click();
                }
            }""")
        except Exception:
            pass

        final_url = active_page.url
        if any(dom in final_url for dom in ["a.hpthek.at", "a.digi4school.at", "a.trauner.at", "a.oebv.at"]):
            break
        if "/ebook/" in final_url and "digi4school.at" not in final_url:
            break

    m = re.search(r"(https?://[^/]+/ebook/[^/?#]+/?)", final_url)
    if m:
        viewer_base_url = m.group(1).rstrip("/") + "/"
    else:
        viewer_base_url = final_url.split("?")[0].rstrip("/") + "/"

    return active_page, viewer_base_url


async def detect_total_pages(page: Page, viewer_base_url: str) -> Optional[int]:
    """Ermittelt die Gesamtzahl der Buchseiten aus dem Viewer."""
    await dismiss_popups(page)
    await page.wait_for_timeout(1500)

    try:
        found_pages = await page.evaluate(r"""() => {
            const candidates = [];
            const elements = Array.from(document.querySelectorAll('span, div, p, label, b, strong'));
            for (const el of elements) {
                if (el.innerText && el.innerText.length < 30) {
                    const m = el.innerText.match(/(?:\/|von)\s*(\d{2,4})\b/i);
                    if (m) {
                        const val = parseInt(m[1]);
                        if (val > 10 && val < 2500) candidates.push(val);
                    }
                }
            }
            if (candidates.length > 0) {
                return Math.max(...candidates);
            }
            return null;
        }""")
        if found_pages and found_pages > 10:
            return int(found_pages)
    except Exception:
        pass

    try:
        thumb_count = await page.evaluate("""() => {
            const thumbs = document.querySelectorAll('#thumbnailPanel a.thumbnail, #thumbnailPanel .thumbnail, a.thumbnail');
            return thumbs ? thumbs.length : 0;
        }""")
        if thumb_count and thumb_count > 10:
            return int(thumb_count)
    except Exception:
        pass

    try:
        js_total = await page.evaluate("""() => {
            return window.totalPages || window.total_pages ||
                   (window.book && window.book.pages ? window.book.pages.length : null) ||
                   (window.PDFViewerApplication ? window.PDFViewerApplication.pagesCount : null);
        }""")
        if js_total and isinstance(js_total, (int, float)) and int(js_total) > 10:
            return int(js_total)
    except Exception:
        pass

    return None


async def extract_table_of_contents(page: Page, viewer_base_url: str) -> List[dict]:
    """Extrahiert das Inhaltsverzeichnis aus dem Viewer."""
    try:
        js_toc = await page.evaluate("""() => {
            function normalizeToc(items, level = 1) {
                if (!Array.isArray(items)) return [];
                const res = [];
                for (const item of items) {
                    if (!item) continue;
                    const title = (item.title || item.name || item.text || item.label || '').trim();
                    let page = item.page || item.pageNumber || item.targetPage || item.pno || null;
                    if (typeof page === 'string') page = parseInt(page);
                    if (title && page && !isNaN(page)) {
                        res.push({ title, page, level });
                    }
                    if (item.subitems || item.children || item.items) {
                        res.push(...normalizeToc(item.subitems || item.children || item.items, level + 1));
                    }
                }
                return res;
            }

            const candidates = [
                window.book && window.book.toc,
                window.book && window.book.navigation,
                window.book && window.book.outline,
                window.toc,
                window.outline,
                window.eBook && window.eBook.toc,
                window.reader && window.reader.toc,
                window.PDFViewerApplication && window.PDFViewerApplication.pdfDocument && window.PDFViewerApplication.pdfDocument.outline
            ];

            for (const cand of candidates) {
                if (cand && Array.isArray(cand) && cand.length > 0) {
                    const norm = normalizeToc(cand);
                    if (norm.length > 0) return norm;
                }
            }
            return null;
        }""")
        if js_toc and len(js_toc) > 0:
            return js_toc
    except Exception:
        pass

    try:
        dom_toc = await page.evaluate(r"""() => {
            const results = [];
            const containers = Array.from(document.querySelectorAll(
                '#tocPanel, #outlineView, #outlinePanel, .toc, nav.toc, [id*="toc"], [class*="toc"], [id*="outline"], [class*="outline"]'
            ));

            for (const container of containers) {
                const items = Array.from(container.querySelectorAll('a, li, div[data-page], .toc-item, .outline-item'));
                for (const el of items) {
                    const rawText = (el.innerText || '').trim();
                    if (!rawText) continue;

                    let targetPage = null;
                    const href = el.getAttribute('href') || '';
                    const dataPage = el.getAttribute('data-page') || el.getAttribute('data-pno') || el.getAttribute('data-page-number');

                    if (dataPage && !isNaN(parseInt(dataPage))) {
                        targetPage = parseInt(dataPage);
                    } else if (href) {
                        const m = href.match(/page=(\d+)/i) || href.match(/#(\d+)/) || href.match(/#page(\d+)/i);
                        if (m) targetPage = parseInt(m[1]);
                    }

                    if (!targetPage) {
                        const mEnd = rawText.match(/(?:[\s.…_]{2,}|\t|\s+)(\d{1,4})$/);
                        if (mEnd) targetPage = parseInt(mEnd[1]);
                    }

                    if (targetPage && targetPage > 0) {
                        const title = rawText.replace(/[\s.…_]{2,}\s*\d{1,4}$/, '').trim();
                        if (title.length >= 2) {
                            let level = 1;
                            if (el.tagName === 'LI' && el.parentElement?.parentElement?.tagName === 'LI') level = 2;
                            if (el.className.includes('sub') || (el.style && (el.style.paddingLeft || el.style.marginLeft))) level = 2;
                            results.push({ title, page: targetPage, level });
                        }
                    }
                }
                if (results.length >= 3) return results;
            }
            return results;
        }""")
        if dom_toc and len(dom_toc) >= 3:
            return dom_toc
    except Exception:
        pass

    endpoint_candidates = [
        f"{viewer_base_url}toc.json",
        f"{viewer_base_url}data/toc.json",
        f"{viewer_base_url}navigation.json"
    ]
    for u in endpoint_candidates:
        try:
            res = await page.evaluate("""async (url) => {
                try {
                    const r = await fetch(url);
                    if (r.ok) return await r.json();
                } catch(e) {}
                return null;
            }""", u)
            if res:
                entries = []
                def parse_json_items(items, lvl=1):
                    if not isinstance(items, list):
                        return
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        t = it.get("title") or it.get("name") or it.get("text") or it.get("label")
                        p = it.get("page") or it.get("pageNumber") or it.get("pno")
                        if t and p:
                            try:
                                entries.append({"title": str(t).strip(), "page": int(p), "level": lvl})
                            except ValueError:
                                pass
                        if "children" in it:
                            parse_json_items(it["children"], lvl + 1)
                        if "subitems" in it:
                            parse_json_items(it["subitems"], lvl + 1)

                if isinstance(res, list):
                    parse_json_items(res)
                elif isinstance(res, dict):
                    parse_json_items(res.get("toc") or res.get("items") or res.get("chapters") or [])

                if len(entries) >= 3:
                    return entries
        except Exception:
            pass

    return []


def crop_dark_viewer_padding(pil_img: Image.Image, max_dark_luma: int = 80) -> Image.Image:
    """Schneidet dunkle Rahmen des Web-Viewers ab und behält weiße Ränder."""
    w, h = pil_img.size
    gray_img = pil_img.convert("L")

    corner_samples = [
        gray_img.getpixel((2, 2)),
        gray_img.getpixel((w - 3, 2)),
        gray_img.getpixel((2, h - 3)),
        gray_img.getpixel((w - 3, h - 3))
    ]

    if any(val > 180 for val in corner_samples):
        return pil_img

    if all(val < max_dark_luma for val in corner_samples):
        thresh = gray_img.point(lambda p: 255 if p > (max_dark_luma + 20) else 0)
        bbox = thresh.getbbox()
        if bbox:
            bw = bbox[2] - bbox[0]
            bh = bbox[3] - bbox[1]
            if bw > (w * 0.4) and bh > (h * 0.4):
                return pil_img.crop(bbox)

    return pil_img


async def capture_single_page(
    page: Page,
    viewer_base_url: str,
    page_num: int,
    max_retries: int = 3,
    timeout: int = 30
) -> Optional[bytes]:
    """Erfasst eine einzelne Buchseite per hochauflösendem Screenshot."""
    target_url = f"{viewer_base_url}?page={page_num}"

    for attempt in range(1, max_retries + 1):
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=timeout * 1000)
            await page.wait_for_timeout(800)
            await dismiss_popups(page)

            page_selectors = [
                f"#pg{page_num} > object",
                f"#pg{page_num}",
                f"#page{page_num}",
                f'div[data-page-number="{page_num}"]',
                f"#pageContainer{page_num}",
                "object[data*='.svg']",
                ".book-page",
                ".page-inner",
                "#viewer .page",
                "main .page",
                "canvas"
            ]

            target_elem: Optional[ElementHandle] = None
            for sel in page_selectors:
                elem = await page.query_selector(sel)
                if elem and await elem.is_visible():
                    box = await elem.bounding_box()
                    if box and box["width"] > 250 and box["height"] > 250:
                        target_elem = elem
                        break

            if target_elem:
                await target_elem.scroll_into_view_if_needed()
                await page.wait_for_timeout(250)
                await dismiss_popups(page)
                img_bytes = await target_elem.screenshot(type="png")
            else:
                await page.wait_for_timeout(400)
                await dismiss_popups(page)
                img_bytes = await page.screenshot(type="png", full_page=False)

            with Image.open(io.BytesIO(img_bytes)) as pil_img:
                cleaned = crop_dark_viewer_padding(pil_img.convert("RGB"))
                out_buf = io.BytesIO()
                cleaned.save(out_buf, format="PNG")
                return out_buf.getvalue()

        except Exception as e:
            if attempt == max_retries:
                logger.warning(f"Seite {page_num} fehlgeschlagen: {e}")
                return None
            await asyncio.sleep(1.5 * attempt)

    return None


def ocr_worker_process(args_tuple: Tuple[int, bytes, str, int, int, str]) -> Tuple[int, bytes]:
    """Multiprocessing Worker für Tesseract OCR (LSTM Engine, OEM 1, PSM 3)."""
    page_num, img_bytes, lang, dpi, psm, tesseract_cmd = args_tuple
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    tess_config = f"--oem 1 --psm {psm} -c user_defined_dpi={dpi} -c preserve_interword_spaces=1"

    try:
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(
            pil_img,
            extension="pdf",
            lang=lang,
            config=tess_config
        )
        return page_num, pdf_bytes
    except Exception:
        pt_w = (pil_img.width / dpi) * 72.0
        pt_h = (pil_img.height / dpi) * 72.0
        doc = fitz.open()
        page = doc.new_page(width=pt_w, height=pt_h)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=93)
        page.insert_image(page.rect, stream=buf.getvalue())
        fallback_bytes = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        return page_num, fallback_bytes


def infer_toc_hierarchy(raw_toc_items: List[dict]) -> List[dict]:
    """Leitet automatisch hierarchische Lesezeichen-Strukturen ab."""
    if not raw_toc_items:
        return []

    module_pattern = re.compile(
        r"^(?:Kompetenzmodul|Modul|Themenbereich|Teil|Abschnitt|Unit|Thema)\b",
        re.IGNORECASE
    )
    has_module_headers = any(module_pattern.search(it.get("title", "")) for it in raw_toc_items)

    processed_items = []
    current_major_level = 1 if not has_module_headers else 2
    seen_first_module = False

    for it in raw_toc_items:
        title = it.get("title", "").strip()
        page = it.get("page", 1)
        orig_level = it.get("level", 1)

        level = orig_level

        if module_pattern.search(title):
            level = 1
            seen_first_module = True
        elif re.match(r"^(?:Kapitel\s+)?\d+\.?\s+[A-Za-zÄÖÜäöüß]", title, re.IGNORECASE):
            level = 2 if has_module_headers else 1
            current_major_level = level
        elif re.match(r"^\d+\.\d+\.?\s+", title):
            level = 3 if has_module_headers else 2
        elif re.match(r"^\d+\.\d+\.\d+\.?\s+", title):
            level = 4 if has_module_headers else 3
        elif re.match(r"^\d+\.\d+\.\d+\.\d+\.?\s+", title):
            level = 5 if has_module_headers else 4
        elif any(title.lower().startswith(kw) for kw in [
            "übersicht", "inhaltsverzeichnis", "inhalt", "vorwort", "geleitwort",
            "impressum", "anhang", "lösungen", "formelsammlung", "stichwort", "index", "register"
        ]):
            level = 1
        else:
            if seen_first_module:
                level = current_major_level + 1
            else:
                level = 1

        processed_items.append({"title": title, "page": page, "level": level})

    final_items = []
    prev_level = 0
    for it in processed_items:
        lvl = it["level"]
        if lvl > prev_level + 1:
            lvl = prev_level + 1
        lvl = max(1, lvl)
        final_items.append({"title": it["title"], "page": it["page"], "level": lvl})
        prev_level = lvl

    return final_items


def apply_table_of_contents(
    doc: fitz.Document,
    raw_toc_items: List[dict],
    downloaded_pages: List[Tuple[int, bytes]]
) -> None:
    """Setzt PDF-Bookmarks und klickbare Hyperlink-Hotspots."""
    orig_to_pdf_pno = {p_num: idx + 1 for idx, (p_num, _) in enumerate(downloaded_pages)}

    if not raw_toc_items:
        toc_pattern = re.compile(r"^([0-9IVX\.\s]*[A-Za-zÄÖÜäöüß][^.]+?)[.\s_…]{2,}\s*(\d{1,4})$", re.MULTILINE)
        extracted_from_ocr = []

        scan_limit = min(12, len(doc))
        for page_idx in range(scan_limit):
            p = doc[page_idx]
            text = p.get_text()
            if any(kw in text.lower() for kw in ["inhaltsverzeichnis", "inhalt"]):
                for match in toc_pattern.finditer(text):
                    title = match.group(1).strip()
                    target_p = int(match.group(2))
                    if len(title) > 2 and target_p > 0:
                        level = 2 if match.group(1).startswith("  ") or title.count(".") > 1 else 1
                        extracted_from_ocr.append({"title": title, "page": target_p, "level": level})

        if extracted_from_ocr:
            raw_toc_items = extracted_from_ocr

    if not raw_toc_items:
        return

    raw_toc_items = infer_toc_hierarchy(raw_toc_items)

    filtered_toc = []
    for item in raw_toc_items:
        orig_page = item["page"]
        if orig_page in orig_to_pdf_pno:
            pdf_pno = orig_to_pdf_pno[orig_page]
            filtered_toc.append([item.get("level", 1), item["title"], pdf_pno])

    if filtered_toc:
        try:
            doc.set_toc(filtered_toc)
        except Exception:
            pass

        scan_limit = min(15, len(doc))
        for page_idx in range(scan_limit):
            p = doc[page_idx]
            page_text = p.get_text().lower()
            is_toc_page = "inhaltsverzeichnis" in page_text or "inhalt" in page_text

            if not is_toc_page:
                matches = sum(1 for _, t, _ in filtered_toc if t.lower() in page_text)
                if matches >= 2:
                    is_toc_page = True

            if is_toc_page:
                linked_y_positions: List[float] = []
                for level, title, target_pdf_pno in filtered_toc:
                    search_snippet = title.strip()
                    if len(search_snippet) > 30:
                        search_snippet = search_snippet[:30]

                    rects = p.search_for(search_snippet)
                    if not rects:
                        words = search_snippet.split()[:3]
                        if len(words) >= 2:
                            rects = p.search_for(" ".join(words))

                    if rects:
                        for r in rects:
                            hotspot_center_y = (r.y0 + r.y1) / 2.0
                            if any(abs(hotspot_center_y - prev_y) < 6 for prev_y in linked_y_positions):
                                continue
                            linked_y_positions.append(hotspot_center_y)

                            hotspot = fitz.Rect(max(0, r.x0 - 5), r.y0 - 2, min(p.rect.width, r.x1 + 80), r.y1 + 2)
                            p.insert_link({
                                "kind": fitz.LINK_GOTO,
                                "page": target_pdf_pno - 1,
                                "from": hotspot
                            })


def detect_page_offset(raw_toc_items: List[dict], doc: fitz.Document) -> int:
    """Ermittelt den Versatz zwischen Buchseiten und physischen PDF-Seiten."""
    diffs: List[int] = []

    if raw_toc_items and len(doc) > 0:
        scan_limit = min(15, len(doc))

        for page_idx in range(scan_limit):
            p = doc[page_idx]
            lines = [line.strip() for line in p.get_text().splitlines() if line.strip()]

            for line in lines:
                if not any(c.isalpha() for c in line):
                    continue

                m_end = re.search(r"\s+(\d{1,4})$", line)
                if not m_end:
                    continue

                printed_p = int(m_end.group(1))
                line_content = line[:m_end.start()].strip()
                clean_line_title = re.sub(r'[\s.…_…,-]+$', '', line_content).strip()
                clean_line_name = re.sub(r'^\d+(?:\.\d+)*\.?\s*', '', clean_line_title).strip().lower()

                if len(clean_line_name) < 4:
                    continue

                for it in raw_toc_items:
                    it_name = re.sub(r'^\d+(?:\.\d+)*\.?\s*', '', it.get("title", "")).strip().lower()
                    if len(it_name) >= 4:
                        if clean_line_name.startswith(it_name) or it_name.startswith(clean_line_name):
                            viewer_p = it.get("page", 0)
                            diff = viewer_p - printed_p
                            if 0 <= diff <= 30:
                                diffs.append(diff)
                            break

    if diffs:
        return max(0, statistics.mode(diffs))

    return 0


def apply_page_labels(
    doc: fitz.Document,
    page_offset: int,
    downloaded_pages: List[Tuple[int, bytes]],
    front_prefix: str = "U"
) -> None:
    """Synchronisiert PDF-Seitenzahlen (Option A: U1, U2... + 1, 2, 3...)."""
    if len(doc) == 0:
        return

    if page_offset <= 0:
        doc.set_page_labels([{"startpage": 0, "prefix": "", "style": "D", "firstpagenum": 1}])
        return

    first_orig_p = downloaded_pages[0][0]
    split_orig_p = page_offset + 1
    labels = []

    split_pdf_idx = None
    for idx, (p_num, _) in enumerate(downloaded_pages):
        if p_num >= split_orig_p:
            split_pdf_idx = idx
            break

    if split_pdf_idx is None:
        labels.append({
            "startpage": 0,
            "prefix": front_prefix,
            "style": "D",
            "firstpagenum": first_orig_p
        })
    elif split_pdf_idx == 0:
        first_printed = first_orig_p - page_offset
        labels.append({
            "startpage": 0,
            "prefix": "",
            "style": "D",
            "firstpagenum": max(1, first_printed)
        })
    else:
        labels.append({
            "startpage": 0,
            "prefix": front_prefix,
            "style": "D",
            "firstpagenum": 1
        })
        labels.append({
            "startpage": split_pdf_idx,
            "prefix": "",
            "style": "D",
            "firstpagenum": 1
        })

    try:
        doc.set_page_labels(labels)
    except Exception:
        pass


class Digi4SchoolService:
    """Service für den vollautomatisierten Download von Digi4School-Büchern."""

    @staticmethod
    def get_default_downloads_dir() -> str:
        """Gibt den Pfad zum Downloads-Ordner des Benutzers zurück."""
        return os.path.join(os.path.expanduser("~"), "Downloads")

    @classmethod
    async def download_book(
        cls,
        email: str,
        password: str,
        code: str,
        output_path: Optional[str] = None,
        pages: Optional[str] = None,
        dpi: int = 300,
        psm: int = 3,
        lang: str = "deu+eng",
        timeout: int = 45,
        retries: int = 3,
        progress_cb: Optional[Callable[[str, int, int, str], None]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Dict[str, Any]:
        """
        Lädt ein Digi4School-Buch herunter und speichert es als durchsuchbare OCR-PDF.

        progress_cb Signatur: progress_cb(phase, current_count, total_count, message_text)
        Phasen: 'login', 'resolving', 'pages', 'ocr', 'toc', 'saving', 'finished'
        """
        def update_progress(phase: str, cur: int, tot: int, msg: str):
            if progress_cb:
                try:
                    progress_cb(phase, cur, tot, msg)
                except Exception:
                    pass

        clean_code = str(code).strip().lower()
        if not clean_code:
            raise ValueError("No access code provided.")

        # 1. Tesseract prüfen (strikt verlangt gemäß User-Vorgabe)
        tess_path = find_tesseract()
        pytesseract.pytesseract.tesseract_cmd = tess_path

        # 2. Output Path ermitteln
        if output_path:
            out_file = Path(output_path)
        else:
            downloads_dir = cls.get_default_downloads_dir()
            out_file = Path(downloads_dir) / f"{clean_code}.pdf"

        out_file.parent.mkdir(parents=True, exist_ok=True)

        update_progress("login", 0, 1, "Signing in to Digi4School...")

        # 3. Playwright starten
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-web-security", "--allow-running-insecure-content"]
            )
            context = await browser.new_context(
                viewport={"width": 2000, "height": 3000},
                device_scale_factor=2,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError("Download cancelled.")

                await login_to_digi4school(page, email, password, timeout=timeout)

                update_progress("resolving", 0, 1, "Loading book and resolving e-book viewer...")
                user_books = await fetch_user_books(page)

                chosen_book = None
                for b in user_books:
                    if b.get("code", "").strip().lower() == clean_code:
                        chosen_book = b
                        break

                if not chosen_book:
                    chosen_book = {"code": clean_code, "title": clean_code}

                book_title = chosen_book.get("title", clean_code)

                # Wenn Standard-Output verwendet wurde und ein echter Buchtitel vorliegt:
                if not output_path and book_title and book_title != clean_code:
                    safe_title = re.sub(r'[\\/*?:"<>|]', '_', book_title).strip()
                    if safe_title:
                        out_file = Path(cls.get_default_downloads_dir()) / f"{safe_title}.pdf"

                active_page, viewer_base_url = await open_book_and_resolve_viewer(
                    context, page, chosen_book, timeout=timeout
                )
                await dismiss_popups(active_page)

                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError("Download cancelled.")

                # Inhaltsverzeichnis aus Viewer laden
                update_progress("resolving", 0, 1, "Loading table of contents and page count...")
                raw_toc_items = await extract_table_of_contents(active_page, viewer_base_url)

                # Gesamtseitenzahl ermitteln
                detected_total = await detect_total_pages(active_page, viewer_base_url)

                if pages:
                    pages_to_fetch = parse_page_ranges(pages, max_pages=detected_total)
                elif detected_total and detected_total > 0:
                    pages_to_fetch = list(range(1, detected_total + 1))
                else:
                    pages_to_fetch = list(range(1, 400))

                total_pages_count = len(pages_to_fetch)
                update_progress("pages", 0, total_pages_count, f"Starting download of {total_pages_count} pages...")

                downloaded_pages: List[Tuple[int, bytes]] = []
                for idx, p_num in enumerate(pages_to_fetch, start=1):
                    if cancel_event and cancel_event.is_set():
                        raise asyncio.CancelledError("Download cancelled.")

                    update_progress(
                        "pages",
                        idx,
                        total_pages_count,
                        f"Downloading page {p_num} ({idx}/{total_pages_count})..."
                    )
                    img_bytes = await capture_single_page(
                        active_page,
                        viewer_base_url,
                        p_num,
                        max_retries=retries,
                        timeout=timeout
                    )
                    if img_bytes:
                        downloaded_pages.append((p_num, img_bytes))

                if not downloaded_pages:
                    raise RuntimeError("Could not capture any book pages.")

                # Einheitliches Format bestimmen
                page_sizes = []
                for _, img_bytes in downloaded_pages:
                    with Image.open(io.BytesIO(img_bytes)) as im:
                        page_sizes.append(im.size)

                median_w = statistics.median([s[0] for s in page_sizes])
                median_h = statistics.median([s[1] for s in page_sizes])
                master_pt_w = (median_w / dpi) * 72.0
                master_pt_h = (median_h / dpi) * 72.0

                # OCR Verarbeitung
                cpu_cores = os.cpu_count() or 4
                max_workers = min(cpu_cores, 12)
                ocr_tasks = [
                    (p_num, img_bytes, lang, dpi, psm, tess_path)
                    for p_num, img_bytes in downloaded_pages
                ]

                update_progress("ocr", 0, len(ocr_tasks), f"Starting OCR on {max_workers} CPU cores...")

                ocr_results = {}
                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(ocr_worker_process, t): t[0] for t in ocr_tasks}
                    done_count = 0
                    for future in as_completed(futures):
                        if cancel_event and cancel_event.is_set():
                            raise asyncio.CancelledError("Download cancelled.")
                        p_num, pdf_page_bytes = future.result()
                        ocr_results[p_num] = pdf_page_bytes
                        done_count += 1
                        update_progress("ocr", done_count, len(ocr_tasks), f"OCR recognition page {p_num} ({done_count}/{len(ocr_tasks)})...")

                update_progress("toc", 0, 1, "Merging pages and creating bookmarks...")
                target_doc = fitz.open()

                for p_num, _ in downloaded_pages:
                    page_pdf_bytes = ocr_results[p_num]
                    src_page_doc = fitz.open("pdf", page_pdf_bytes)
                    src_page = src_page_doc[0]

                    dest_page = target_doc.new_page(width=master_pt_w, height=master_pt_h)
                    scale = min(master_pt_w / src_page.rect.width, master_pt_h / src_page.rect.height)
                    pw = src_page.rect.width * scale
                    ph = src_page.rect.height * scale
                    x0 = (master_pt_w - pw) / 2.0
                    y0 = (master_pt_h - ph) / 2.0
                    dest_rect = fitz.Rect(x0, y0, x0 + pw, y0 + ph)

                    dest_page.show_pdf_page(dest_rect, src_page_doc, 0)
                    src_page_doc.close()

                # Inhaltsverzeichnis & Hotspots
                apply_table_of_contents(target_doc, raw_toc_items, downloaded_pages)

                # Page Labels (Seitennummern synchronisieren)
                detected_offset = detect_page_offset(raw_toc_items, target_doc)
                apply_page_labels(target_doc, detected_offset, downloaded_pages, front_prefix="U")

                update_progress("saving", 0, 1, f"Saving PDF document ({out_file.name})...")
                target_doc.save(str(out_file), garbage=4, deflate=True)
                target_doc.close()

                file_size_mb = out_file.stat().st_size / (1024 * 1024)
                update_progress("finished", total_pages_count, total_pages_count, f"Successfully saved ({file_size_mb:.1f} MB)")

                return {
                    "success": True,
                    "title": book_title,
                    "code": clean_code,
                    "path": str(out_file.resolve()),
                    "pages": len(downloaded_pages),
                    "size_mb": round(file_size_mb, 2),
                    "offset": detected_offset
                }

            finally:
                await browser.close()
