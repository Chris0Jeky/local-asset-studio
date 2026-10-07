"""Run decisions remain reachable without replacing execution owners (#770/#775/#778/#779)."""
import workshop_entry_points as entry
from workshop_entry_points import workshop_html, script


class RunDecisions(entry.EntryPoints):
    def load_workshop(self, touch=False):
        if touch:
            self.page.close()
            self.page = self.browser.new_page(viewport={'width': 390, 'height': 844}, has_touch=True)
            self.page.on('pageerror', lambda error: self.errors.append(str(error)))
            self.page.set_default_timeout(3000)
        html = workshop_html().replace(script('workshop.js'), '''<script>
window.runOriginals=Object.fromEntries(['generate','batch','randomSeed','planComparison'].map(id=>[id,document.getElementById(id)]));
window.comparisonPlans=0;
document.getElementById('randomSeed').onclick=()=>{document.querySelector('[data-key="seed"]').value=43;document.dispatchEvent(new Event('studio:recipe'));};
document.getElementById('planComparison').onclick=()=>comparisonPlans++;
</script>''' + script('workshop.js'))
        self.page.set_content(html)
        self.page.wait_for_selector('#workshopRecipeChange')

    def test_secondary_decisions_are_visible_and_keep_original_handlers(self):
        self.load_workshop()
        self.page.fill('#positive', 'My untouched idea')
        for layout in ('focus', 'studio', 'immersive'):
            with self.subTest(layout=layout):
                self.page.select_option('#workshopLayout', layout, force=True)
                for identity in ('generate', 'batch', 'randomSeed', 'planComparison'):
                    self.assertEqual(self.page.locator('#'+identity).count(), 1)
                    self.assertTrue(self.page.locator('#'+identity).evaluate('(n)=>n===runOriginals[n.id]'))
                    self.assertTrue(self.page.locator('#'+identity).is_visible(), identity)
                self.assertFalse(self.page.locator('#workshopChecks').evaluate('(n)=>n.open'))
                self.page.click('#randomSeed')
                self.assertEqual(self.page.locator('[data-key=seed]').input_value(), '43')
                self.page.click('#planComparison')
                self.assertEqual(self.page.locator('#positive').input_value(), 'My untouched idea')
                self.assertEqual(self.page.evaluate('submitted'), 0)
        self.assertEqual(self.page.evaluate('comparisonPlans'), 3)

    def test_decisions_fit_short_and_narrow_viewports_with_long_blockers(self):
        self.load_workshop()
        self.page.evaluate("document.querySelector('#uxBlockers p').textContent='A long readiness reason '.repeat(30);document.querySelector('#status').textContent='Details '.repeat(200);document.querySelector('#estimateValue').textContent='~42s'")
        for width, height in ((1440, 900), (1280, 720), (640, 360), (390, 844), (320, 568)):
            self.page.set_viewport_size({'width': width, 'height': height})
            for layout in ('focus', 'studio', 'immersive'):
                with self.subTest(width=width, height=height, layout=layout):
                    self.page.select_option('#workshopLayout', layout, force=True)
                    for identity in ('generate', 'randomSeed', 'planComparison', 'workshopEta'):
                        self.assertTrue(self.page.locator('#'+identity).is_visible(), identity)
                        box = self.page.locator('#'+identity).bounding_box()
                        self.assertGreaterEqual(box['x'], 0, identity)
                        self.assertGreaterEqual(box['y'], 0, identity)
                        self.assertLessEqual(box['x']+box['width'], width, identity)
                        self.assertLessEqual(box['y']+box['height'], height, identity)
                    self.assertIn('~42s', self.page.locator('#workshopEta').inner_text())
                    self.assertTrue(self.page.locator('#generate').is_disabled())
                    self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)

    def test_focused_text_field_is_never_left_under_the_dock(self):
        """Handoff 03: the fixed dock covered the prompt at 1440x900 and half the phone screen."""
        self.load_workshop()
        # Room above and below, so any field can be scrolled to sit on the dock's top edge.
        self.page.evaluate("document.querySelector('#createView').insertAdjacentHTML('beforebegin','<div style=height:900px></div>');document.querySelector('#createView').style.paddingBottom='900px'")
        overlap = """(id)=>{const f=document.getElementById(id).getBoundingClientRect(),d=document.querySelector('.wk-run-dock').getBoundingClientRect();
          return {covered:Math.max(0,Math.min(f.bottom,d.bottom)-Math.max(f.top,d.top)),top:f.top,dock:d.height}}"""
        # 720x450 is 1440x900 at 200 % zoom; 640x360 is the shortest supported size.
        for width, height in ((1440, 900), (1280, 720), (720, 450), (640, 360), (390, 844)):
            self.page.set_viewport_size({'width': width, 'height': height})
            for layout in ('focus', 'studio', 'immersive'):
                for field in ('positive', 'negative'):
                    with self.subTest(width=width, height=height, layout=layout, field=field):
                        self.page.select_option('#workshopLayout', layout, force=True)
                        self.page.locator('#negativeWrap').evaluate('(n)=>n.open=true')
                        self.page.evaluate("document.activeElement?.blur()")
                        before = self.page.locator('.wk-run-dock').bounding_box()['height']
                        # Put the field's top just above the dock, the way a scrolled page leaves it, then click into it.
                        self.page.evaluate("""([id,h])=>{const f=document.getElementById(id),d=document.querySelector('.wk-run-dock');
                          scrollBy(0,f.getBoundingClientRect().top-(d.getBoundingClientRect().top-30))}""", [field, height])
                        self.assertGreater(self.page.evaluate(overlap, field)['covered'], 0)
                        self.page.click('#'+field, position={'x': 20, 'y': 10})
                        self.page.wait_for_timeout(120)
                        result = self.page.evaluate(overlap, field)
                        self.assertEqual(result['covered'], 0, result)
                        self.assertGreaterEqual(result['top'], 0, result)
                        self.assertTrue(self.page.locator('#generate').is_visible())
                        if width <= 600 or height <= 700: self.assertLess(result['dock'], before, 'a narrow or short dock compacts while typing')
                        self.page.evaluate("document.activeElement?.blur()")
                        self.assertTrue(self.page.locator('#planComparison').is_visible())
        self.assertEqual(self.page.evaluate('submitted'), 0)

    def test_a_press_that_leaves_a_text_field_lands_on_its_control(self):
        """#1229: leaving the prompt grows the compact dock; mid-press, that moved a dock control under the pointer and ate the click."""
        self.load_workshop()
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.select_option('#workshopLayout', 'focus', force=True)
        self.page.evaluate("document.activeElement?.blur()")
        full = self.page.evaluate("""()=>[...document.querySelectorAll('.wk-run-dock :is(button,select,input)')].filter(n=>n.offsetParent)
          .map(n=>{const r=n.getBoundingClientRect();return {top:r.top,left:r.left,width:r.width}})""")
        self.page.click('#positive', position={'x': 20, 'y': 10})
        self.page.wait_for_timeout(120)
        compact = self.page.evaluate("document.querySelector('.wk-run-dock').getBoundingClientRect().top")
        # A dock control whose full-size position rises above the compact dock's top edge.
        target = min(full, key=lambda r: r['top'])
        self.assertLess(target['top'] + 12, compact, 'the premise: the full dock reaches above the compact one')
        # A page control visible just above the compact dock, where that dock control lands once the dock grows.
        self.page.evaluate("""([r,bottom])=>{window.pressed=0;const b=document.createElement('button');b.id='pressProbe';b.type='button';b.textContent='Probe';
          b.style.cssText='position:fixed;z-index:1;margin:0;left:'+r.left+'px;width:'+r.width+'px;top:'+(r.top+2)+'px;height:'+(bottom-r.top-4)+'px';
          b.onclick=()=>pressed++;document.getElementById('createView').append(b)}""", [target, compact])
        self.assertTrue(self.page.locator('#positive').evaluate('(n)=>n===document.activeElement'))
        self.page.locator('#pressProbe').click()
        self.assertEqual(self.page.evaluate('pressed'), 1, 'the click lands on the control the press started on')
        self.page.wait_for_function("!document.querySelector('.wk-run-dock').classList.contains('wk-typing')")
        self.assertLess(self.page.evaluate("document.querySelector('.wk-run-dock').getBoundingClientRect().top"), compact, 'the dock relaxes after the press')
        # Focus moving between text fields keeps the dock compact.
        self.page.click('#positive', position={'x': 20, 'y': 10})
        self.page.locator('#negativeWrap').evaluate('(n)=>n.open=true')
        self.page.click('#negative', position={'x': 20, 'y': 10})
        self.page.wait_for_timeout(50)
        self.assertTrue(self.page.evaluate("document.querySelector('.wk-run-dock').classList.contains('wk-typing')"))
        # A release the window never sees (Alt+Tab mid-press) still relaxes the dock once the window loses focus.
        self.page.evaluate("dispatchEvent(new PointerEvent('pointerdown'));document.getElementById('pressProbe').focus()")
        self.assertTrue(self.page.evaluate("document.querySelector('.wk-run-dock').classList.contains('wk-typing')"), 'held while the press lasts')
        self.page.evaluate("dispatchEvent(new Event('blur'))")
        self.page.wait_for_function("!document.querySelector('.wk-run-dock').classList.contains('wk-typing')")
        self.assertEqual(self.page.evaluate('submitted'), 0)

    def test_a_touch_tap_that_leaves_a_text_field_lands_on_its_control(self):
        """#1245: a touch pointerup precedes the compatibility click, so the compact dock must hold until that click."""
        self.load_workshop(touch=True)
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.select_option('#workshopLayout', 'focus', force=True)
        self.page.evaluate("document.activeElement?.blur()")
        full = self.page.evaluate("""()=>[...document.querySelectorAll('.wk-run-dock :is(button,select,input)')].filter(n=>n.offsetParent)
          .map(n=>{const r=n.getBoundingClientRect();return {top:r.top,left:r.left,width:r.width}})""")
        self.page.focus('#positive')
        self.page.wait_for_timeout(120)
        compact = self.page.evaluate("document.querySelector('.wk-run-dock').getBoundingClientRect().top")
        target = min(full, key=lambda r: r['top'])
        self.assertLess(target['top'] + 12, compact, 'the premise: the full dock reaches above the compact one')
        self.page.evaluate("""([r,bottom])=>{window.pressed=0;const b=document.createElement('button');b.id='pressProbe';b.type='button';b.textContent='Probe';
          b.style.cssText='position:fixed;z-index:1;margin:0;left:'+r.left+'px;width:'+r.width+'px;top:'+(r.top+2)+'px;height:'+(bottom-r.top-4)+'px';
          b.onclick=()=>pressed++;document.getElementById('createView').append(b)}""", [target, compact])
        self.assertTrue(self.page.locator('#positive').evaluate('(n)=>n===document.activeElement'))
        self.page.tap('#pressProbe')
        self.assertEqual(self.page.evaluate('pressed'), 1, 'the tap lands on the control under the finger')
        self.page.wait_for_function("!document.querySelector('.wk-run-dock').classList.contains('wk-typing')")
        self.assertLess(self.page.evaluate("document.querySelector('.wk-run-dock').getBoundingClientRect().top"), compact, 'the dock relaxes after the tap')
        self.assertEqual(self.page.evaluate('submitted'), 0)

    def test_no_seed_control_has_no_dead_randomize_button(self):
        self.load_workshop()
        self.page.locator('[data-key=seed]').evaluate('(n)=>n.remove()')
        self.page.evaluate("document.querySelector('#createView').__workshop.sync()")
        self.assertFalse(self.page.locator('#randomSeed').is_visible())


    def test_every_blocker_is_listed_with_its_fix_not_only_the_first(self):
        """Handoff 03: Create showed only the first blocker; the full list sat in a collapsed disclosure."""
        self.load_workshop()
        self.page.evaluate("""document.getElementById('uxBlockers').innerHTML=
          '<div class="ux-blocker" data-readiness-code="models"><p>Connect your local model environment before generating.</p></div>'+
          '<div class="ux-blocker" data-readiness-code="references"><p>Attach every required reference before starting.</p><button type="button" data-ux-resolve="references">Show the empty slot</button></div>'+
          '<div class="ux-blocker" data-readiness-code="parameters"><p>Width must be a multiple of 8.</p><button type="button" data-ux-resolve="parameters">Review motion settings</button></div>'""")
        self.page.wait_for_function("document.querySelectorAll('#workshopBlockerList li').length===3")
        dock = self.page.locator('#workshopReadiness').inner_text()
        self.assertIn('Connect your local model environment', dock)
        self.assertIn('+2 more', dock)
        self.assertFalse(self.page.locator('#workshopChecks').evaluate('(n)=>n.open'))
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': height})
                items = self.page.locator('#workshopBlockerList li')
                self.assertEqual(items.count(), 3)
                self.assertTrue(items.nth(2).is_visible())
                self.assertIn('3 things to fix', self.page.locator('#workshopSetupReadiness').inner_text())
                self.assertIn('Width must be a multiple of 8.', items.nth(2).inner_text())
                self.assertEqual(items.nth(0).locator('button').count(), 0, 'no fix button is invented')
        # The fix button forwards to the original readiness action; it owns no behaviour of its own.
        self.page.locator('#workshopBlockerList li').nth(2).locator('button').click()
        self.assertTrue(self.page.locator('[data-key="width"]').evaluate('(n)=>n===document.activeElement'))
        # A repeat render with identical evidence keeps the same nodes (no focus loss on poll).
        node = self.page.evaluate_handle("document.querySelector('#workshopBlockerList li')")
        self.page.evaluate("document.querySelector('#createView').__workshop.sync()")
        self.assertTrue(self.page.evaluate("(n)=>n.isConnected", node))
        # Codex P2 on #1125: once one blocker is left, its repair stays in the strip (once, beside its summary).
        self.page.evaluate("document.getElementById('uxBlockers').innerHTML='<div class=\"ux-blocker\" data-readiness-code=\"parameters\"><p>Width must be a multiple of 8.</p><button type=\"button\" data-ux-resolve=\"parameters\">Review motion settings</button></div>'")
        self.page.wait_for_function("document.querySelectorAll('#workshopBlockerList li').length===1 && !document.getElementById('workshopBlockerList').hidden")
        self.assertEqual(self.page.locator('#workshopReadiness').inner_text(), 'Width must be a multiple of 8.')
        self.assertEqual(self.page.locator('#workshopSetupReadiness').inner_text(), 'Width must be a multiple of 8.')
        self.assertEqual(self.page.locator('#workshopBlockerList li').inner_text(), 'Review motion settings', 'the message is not repeated')
        self.page.evaluate("document.activeElement?.blur()")
        self.page.locator('#workshopBlockerList button').click()
        self.assertTrue(self.page.locator('[data-key="width"]').evaluate('(n)=>n===document.activeElement'))
        self.page.evaluate("document.getElementById('uxBlockers').innerHTML='<div class=\"ux-blocker\"><p>Only this one.</p></div>'")
        self.page.wait_for_function("document.getElementById('workshopBlockerList').hidden")
        self.assertEqual(self.page.locator('#workshopReadiness').inner_text(), 'Only this one.')
        self.assertEqual(self.page.locator('#workshopSetupReadiness').inner_text(), 'Only this one.')
        self.assertEqual(self.page.evaluate('submitted'), 0)

if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=2)
