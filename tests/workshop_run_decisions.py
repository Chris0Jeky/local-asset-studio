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

    def test_no_seed_control_has_no_dead_randomize_button(self):
        self.load_workshop()
        self.page.locator('[data-key=seed]').evaluate('(n)=>n.remove()')
        self.page.evaluate("document.querySelector('#createView').__workshop.sync()")
        self.assertFalse(self.page.locator('#randomSeed').is_visible())


if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=2)
