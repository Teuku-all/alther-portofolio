"""Run: python tests/motion_smoke.py (requires playwright and Microsoft Edge)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(__import__('tempfile').gettempdir()) / 'portfolio-motion-review'
ARTIFACTS.mkdir(exist_ok=True)
URL = ROOT.joinpath('index.html').as_uri()

def verify(page, width, height, mobile=False, reduced=False):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('crash', lambda: errors.append('Browser page crashed'))
    page.goto(URL)
    page.wait_for_timeout(300)
    page.evaluate("document.fonts.ready")
    assert page.locator('.fan-card').count() == 9
    page.locator('#work').scroll_into_view_if_needed()
    page.wait_for_timeout(750)
    # Repeated navigation must settle to the selected project and matching details.
    page.evaluate("for (let i=0; i<24; i++) document.getElementById('fanNext').click()")
    page.wait_for_timeout(800)
    state = page.evaluate("({current, title: piTitle.textContent, expected: projects[current].t[lang].title, selected: document.querySelectorAll('.fan-card[data-pos=\"0\"]').length})")
    assert state['selected'] == 1 and state['title'] == state['expected'], state
    # Language and theme transitions can be requested together, including repeated clicks.
    page.evaluate("for (let i=0; i<10; i++) { themeBtn.click(); setLang(i%2 ? 'id' : 'en'); }")
    page.wait_for_function("!themeBusy && !root.classList.contains('lang-vt')")
    assert page.evaluate("!themeBusy && !root.classList.contains('lang-vt')")
    page.evaluate("setLang('id')")
    page.wait_for_timeout(650)
    page.locator('#skills').scroll_into_view_if_needed()
    page.wait_for_timeout(750)
    assert 'Cyber' in page.locator('[data-i18n=cap2_cat]').text_content()
    assert page.locator('[data-i18n=sk_title]').inner_text().replace('\n', ' ') == 'Yang Bisa Saya Lakukan'
    # Decorative motion is actually paused away from the viewport.
    assert page.evaluate("getComputedStyle(document.querySelector('#hero .mq-row')).animationPlayState === 'paused' || getComputedStyle(document.querySelector('#hero .mq-row')).animationName === 'none'")
    if width <= 900:
        page.locator('#menuBtn').click()
        page.wait_for_timeout(350)
        assert page.locator('#mobMenu').get_attribute('aria-hidden') == 'false'
        assert page.evaluate("root.classList.contains('menu-open') && document.activeElement.id === 'mobClose'")
        page.keyboard.press('Escape')
        assert page.locator('#mobMenu').get_attribute('aria-hidden') == 'true'
        # A resize while the menu is open must release scrolling on desktop.
        page.locator('#menuBtn').click()
        page.set_viewport_size({'width': 1000, 'height': height})
        page.wait_for_timeout(350)
        assert page.evaluate("!root.classList.contains('menu-open') && mobMenu.inert")
        page.set_viewport_size({'width': width, 'height': height})
        # A mostly vertical touch gesture must not advance the gallery.
        page.locator('#work').scroll_into_view_if_needed()
        result = page.evaluate('''() => {
          const before=current;
          const send=(type,x,y)=>carousel.dispatchEvent(new PointerEvent(type, {bubbles:true,isPrimary:true,pointerId:23,pointerType:'touch',button:0,clientX:x,clientY:y}));
          send('pointerdown',100,100); send('pointermove',152,240); send('pointerup',155,250);
          const vertical = current === before;
          send('pointerdown',250,100); send('pointermove',100,105); send('pointerup',90,105);
          return {vertical, horizontal:current === (before+1)%total};
        }''')
        assert all(result.values()), result
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_timeout(100)
    assert page.evaluate('reduce')
    assert page.evaluate("getComputedStyle(document.querySelector('.project-ribbon-track')).animationName") == 'none'
    page.emulate_media(reduced_motion='reduce' if reduced else 'no-preference')
    # All content must remain reachable; no page-wide horizontal overflow at any section.
    for section in ['#hero', '#work', '#skills', '#about', '#project-ribbons', '#contact']:
        page.locator(section).scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (width, section)
        if section in ['#skills', '#project-ribbons']:
            page.screenshot(path=str(ARTIFACTS / f'{width}-{section[1:]}.png'))
    assert not errors, errors
    print(json.dumps({'width':width,'mobile':mobile,'reduced':reduced,'errors':errors,'status':'PASS'}))

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    for width, height, mobile, reduced in [(320,740,True,False),(390,844,True,False),(768,1024,False,False),(1440,900,False,False),(1920,1080,False,True)]:
        context=browser.new_context(viewport={'width':width,'height':height}, is_mobile=mobile, has_touch=mobile, reduced_motion='reduce' if reduced else 'no-preference')
        page=context.new_page()
        verify(page,width,height,mobile,reduced)
        context.close()
    # Graceful fallback without canvas or View Transitions.
    context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page=context.new_page()
    page.add_init_script("document.startViewTransition = undefined; HTMLCanvasElement.prototype.getContext = () => null;")
    verify(page,390,844,True,False)
    context.close()
    # The content stays readable when JavaScript cannot run.
    context=browser.new_context(java_script_enabled=False,viewport={'width':390,'height':844})
    page=context.new_page(); page.goto(URL)
    assert page.locator('[data-i18n=sk_title]').is_visible()
    assert page.locator('[data-i18n=cap2_cat]').is_visible()
    context.close()
    browser.close()
print(f'Screenshots: {ARTIFACTS}')

