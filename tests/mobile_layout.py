"""Mobile layout regression checks. Run: python tests/mobile_layout.py"""
from pathlib import Path
import json
import tempfile
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(tempfile.gettempdir()) / 'portfolio-mobile-layout'
OUTPUT.mkdir(exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    for width, height in [(320,568),(375,667),(390,844),(430,932),(640,360),(844,390)]:
        context = browser.new_context(viewport={'width':width,'height':height}, is_mobile=True, has_touch=True, reduced_motion='reduce')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('crash', lambda: errors.append('Page crashed'))
        page.goto(ROOT.joinpath('index.html').as_uri())
        page.evaluate('document.fonts.ready')
        for language in ['id','en']:
            page.evaluate('(language) => setLang(language)', language)
            for theme in ['dark','light']:
                page.evaluate('(theme) => applyTheme(theme)', theme)
                # Measure content boxes rather than relying on overflow-x:clip hiding bugs.
                for section in ['#hero','#work','#skills','#about','#contact']:
                    page.locator(section).scroll_into_view_if_needed()
                    page.wait_for_timeout(100)
                    outside = page.evaluate('''() => [...document.querySelectorAll('nav,.work-header,.fan-controls,.proj-info-title,.proj-info-desc,.tech-grid,.cap-desc,.cap-tags,.about-profile,.currently-bar,.traits-cloud,.cta-btns,footer')].filter(e => {
                      const r=e.getBoundingClientRect();return r.left < -1 || r.right > innerWidth+1 || e.scrollWidth > e.clientWidth+2;
                    }).map(e=>e.className || e.tagName)''')
                    assert not outside, (width,language,theme,outside)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                controls = page.locator('.fan-dot, .fan-arrow, #themeBtn, #menuBtn').evaluate_all('(items)=>items.map(e=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))')
                assert all(x['w'] >= 24 and x['h'] >= 24 for x in controls), (width,controls)
                assert page.locator('.tech-logo span').first.evaluate('(e)=>getComputedStyle(e).opacity') == '1'
                # Short landscape viewport: all menu options and close control are reachable.
                page.locator('#menuBtn').click()
                for link in page.locator('#mobMenu a').all():
                    link.scroll_into_view_if_needed()
                    r = link.bounding_box()
                    assert r['y'] >= 0 and r['y']+r['height'] <= height+1, (width,r)
                    assert link.evaluate('(e)=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}')
                page.locator('#mobClose').click()
                assert page.evaluate('!root.classList.contains("menu-open") && mobMenu.inert')
                # Actual anchor navigation closes the menu and keeps section headings below navbar.
                page.locator('#menuBtn').click()
                page.locator('#mobMenu a[href="#skills"]').click()
                page.wait_for_timeout(120)
                assert page.evaluate('!root.classList.contains("menu-open")')
                heading = page.locator('[data-i18n=sk_title]').bounding_box()
                nav = page.locator('#mainNav').bounding_box()
                assert heading['y'] >= nav['height']-1, (width,heading,nav)
            # Mobile text zoom: content must remain readable without horizontal clipping.
            page.add_style_tag(content='html { font-size: 20px; }')
            page.locator('#contact').scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
            page.add_style_tag(content='html { font-size: 16px; }')
        page.locator('#work').scroll_into_view_if_needed()
        page.wait_for_timeout(100)
        page.screenshot(path=str(OUTPUT / f'{width}-gallery.png'))
        page.locator('#menuBtn').click()
        page.wait_for_function("getComputedStyle(document.getElementById('mobMenu')).opacity === '1'")
        page.screenshot(path=str(OUTPUT / f'{width}-menu.png'))
        assert not errors, errors
        print(json.dumps({'viewport':f'{width}x{height}','languages':2,'themes':2,'errors':errors,'status':'PASS'}), flush=True)
        context.close()
    browser.close()
print(f'Screenshots: {OUTPUT}')
