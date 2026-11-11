"""Test bổ sung cho cải tiến bonus của agent: retry budget 429, rút gọn context, ghi chú pagination."""
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import run_agent, MAX_RATE_LIMIT_ATTEMPTS
from bonus.tools import BonusTools
from test_agent import ScriptedProvider, call, final


class BonusAgentExtraTests(unittest.TestCase):
    def test_retry_budget_blocks_fourth_429_call(self):
        t = BonusTools(scenario='rate_limit_always')
        p = ScriptedProvider([call(f'c{i}', 'get_vercel_status', {}) for i in range(4)] + [final('Không xác định được Vercel.')])
        result = run_agent('Kiểm tra Vercel', p, t, max_steps=6)
        self.assertEqual(result['status'], 'completed')
        executed = [e for e in result['trace'] if e['event'] == 'tool' and e['name'] == 'get_vercel_status']
        blocked = [e for e in result['trace'] if e['event'] == 'tool_blocked']
        self.assertEqual(len(executed), MAX_RATE_LIMIT_ATTEMPTS)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(json.loads(p.histories[4][-1]['content'])['error'], 'RETRY_BUDGET_EXHAUSTED')
        self.assertIn('KHÔNG phải outage', json.loads(p.histories[1][-1]['content'])['agent_note'])

    def test_noisy_list_is_compacted_before_context(self):
        t = BonusTools(scenario='noisy')
        p = ScriptedProvider([call('a', 'get_vercel_status', {}), final()])
        result = run_agent('Kiểm tra Vercel', p, t, max_steps=3)
        sent = json.loads(p.histories[1][-1]['content'])
        self.assertEqual(len(sent['distractors']), 3)
        self.assertIn('agent_context_note', sent)
        self.assertEqual(result['trace'][1]['compacted'], {'distractors': 157})

    def test_pagination_note_when_more_pages(self):
        t = BonusTools()
        args = {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg', 'offset': 0, 'limit': 2}
        url = t.execute('get_incident_details', args)['url']
        p = ScriptedProvider([call('a', 'get_incident_details', args), final('Nguồn: ' + url)])
        run_agent('Timeline Vercel', p, t, max_steps=3)
        sent = json.loads(p.histories[1][-1]['content'])
        self.assertIsNotNone(sent['next_offset'])
        self.assertIn('next_offset', sent['agent_note'])


if __name__ == '__main__':
    unittest.main()
