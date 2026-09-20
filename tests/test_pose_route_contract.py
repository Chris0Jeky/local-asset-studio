import unittest
from studio_workflow import pose_route_contract as contracts


class PoseRouteContractTests(unittest.TestCase):
    def test_projections_share_one_klein_semantics(self):
        screening = contracts.screening_projection('klein-geometry')
        binding = contracts.binding_projection('klein-geometry')
        self.assertEqual(screening['input_representation'], 'precomputed-skeleton')
        self.assertEqual(binding['source_kind'], 'precomputed-skeleton')
        self.assertEqual(screening['detector_behavior'], 'not-applicable')
        self.assertEqual(binding['detector_behavior'], 'not-applicable')
        self.assertEqual(screening['mechanism'], binding['mechanism'])
        self.assertEqual(screening['pins'], binding['pins'])
        self.assertEqual(screening['backend_ids'], binding['backend_ids'])

    def test_every_projection_matches_the_frozen_contract(self):
        self.assertEqual(contracts.ROUTE_IDS, (
            'klein-geometry', 'copy-pose', 'sdxl-corrected-skeleton'))
        self.assertEqual(contracts.KNOWN_BACKEND_IDS, ('primary', 'hidream', 'h3'))
        for route_id in contracts.ROUTE_IDS:
            with self.subTest(route_id=route_id):
                contract = contracts.route_contract(route_id)
                screening = contracts.screening_projection(route_id)
                binding = contracts.binding_projection(route_id)
                self.assertEqual(screening['id'], route_id)
                self.assertEqual(screening['input_representation'], contract.source_representation)
                self.assertEqual(binding['source_kind'], contract.source_representation)
                self.assertEqual(binding['native_slot'], contract.native_slot)
                self.assertEqual(binding['formats'], contract.formats)
                for backend_id in contracts.KNOWN_BACKEND_IDS:
                    self.assertEqual(
                        contracts.validate_backend(route_id, backend_id), backend_id)

    def test_projection_mutation_cannot_change_canonical_contract(self):
        projection = contracts.binding_projection('copy-pose')
        projection['mechanism'] = 'changed'
        self.assertEqual(
            contracts.binding_projection('copy-pose')['mechanism'],
            'copy-pose-rgb')

    def test_unknown_route_and_backend_typo_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            contracts.route_contract('unknown')
        with self.assertRaisesRegex(ValueError, 'not configured'):
            contracts.validate_backend('copy-pose', 'primry')


if __name__ == '__main__':
    unittest.main()
