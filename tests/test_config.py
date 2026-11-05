"""Local configuration tests use dummy values and never contact inference."""
from pathlib import Path
import tempfile
import unittest
from trustbound.config import load_local_env


class ConfigTests(unittest.TestCase):
    def test_process_values_override_local_file_including_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('VULTR_INFERENCE_API_KEY=local-dummy\nVULTR_MODEL=local-model\nPATH=ignored\n', encoding='utf-8')
            env = {'VULTR_INFERENCE_API_KEY': 'injected-dummy', 'VULTR_MODEL': ''}
            load_local_env(path, env)
            self.assertEqual(env, {'VULTR_INFERENCE_API_KEY': 'injected-dummy', 'VULTR_MODEL': ''})

    def test_quotes_bom_comments_and_export_without_interpolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('\ufeff# local\nexport VULTR_INFERENCE_API_KEY="dummy#literal" # comment\nVULTR_MODEL=unit-model # note\nTRUSTBOUND_ENABLE_LIVE=1\n', encoding='utf-8')
            env = {}
            load_local_env(path, env)
            self.assertEqual(env['VULTR_INFERENCE_API_KEY'], 'dummy#literal')
            self.assertEqual(env['VULTR_MODEL'], 'unit-model')
            self.assertEqual(env['TRUSTBOUND_ENABLE_LIVE'], '1')

    def test_production_opt_out_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            load_local_env(path, {})
            path.write_text('VULTR_INFERENCE_API_KEY=dummy', encoding='utf-8')
            env = {'TRUSTBOUND_LOAD_DOTENV': '0'}
            load_local_env(path, env)
            self.assertNotIn('VULTR_INFERENCE_API_KEY', env)
