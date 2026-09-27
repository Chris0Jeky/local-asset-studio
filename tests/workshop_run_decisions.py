"""Run decisions remain reachable without replacing execution owners (#770/#775/#778/#779)."""
import workshop_entry_points as entry
from workshop_entry_points import workshop_html, script


class RunDecisions(entry.EntryPoints):
    def load_workshop(self):
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
        for width, height in ((1440, 900), (1280, 720), (390, 844)):
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
                        if width <= 600: self.assertLess(result['dock'], before, 'the narrow dock compacts while typing')
                        self.page.evaluate("document.activeElement?.blur()")
                        self.assertTrue(self.page.locator('#planComparison').is_visible())
        self.assertEqual(self.page.evaluate('submitted'), 0)

    def test_no_seed_control_has_no_dead_randomize_button(self):
        self.load_workshop()
        self.page.locator('[data-key=seed]').evaluate('(n)=>n.remove()')
        self.page.evaluate("document.querySelector('#createView').__workshop.sync()")
        self.assertFalse(self.page.locator('#randomSeed').is_visible())


if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=2)
