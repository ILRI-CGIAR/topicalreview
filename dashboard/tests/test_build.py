"""Offline regression tests for CGIAR dashboard release contract; synthetic rows only."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build as app

class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract=json.loads(app.CONTRACT.read_text(encoding='utf-8'))

    def test_country_parsing_and_rejection(self):
        self.assertEqual(app.parse_country('TGO, BEN'),['BEN','TGO'])
        with self.assertRaises(ValueError):app.parse_country('US')

    def test_multiword_and_missing_product_handling(self):
        self.assertEqual(app.parse_names('Rice, Tree (Oak, pine); Millet',preserve_parentheses=True),
                         ['Rice','Tree (Oak, pine)','Millet'])
        self.assertEqual(app.parse_names('Rice, Not reported, Millet'),['Rice','Millet'])

    def test_crop_sentence_case_normalisation(self):
        self.assertEqual(app.sentence_case_product('rice'), 'Rice')
        self.assertEqual(app.sentence_case_product('RICE'), 'Rice')
        names=app.parse_names('Rice, rice; RICE')
        self.assertEqual({app.sentence_case_product(n) for n in names}, {'Rice'})

    def test_adaptation_merge_is_frozen(self):
        merged='2. Autonomous/unplanned adaptation (Spontaneous responses by individuals. communities. or systems without formal planning)'
        self.assertEqual(app.extract_code_values(merged,{'1','2','4','5'},'Adaptation nature'),['2'])
        with self.assertRaises(ValueError):app.extract_code_values('3. Unplanned or reactive adaptation',{'1','2','4','5'},'Adaptation nature')

    def test_synthetic_record_and_unknown_themes_fail(self):
        row={k:'' for k in self.contract['expected_columns']}
        row.update({'Filenames':'synthetic_test.pdf','Title':'Synthetic test article','Year':'2021',
                    'Country':'IND','Crop/livestock/tree/fish':'Crop',
                    'Crop/livestock/tree/fish name (CLEAN)':'Rice; Wheat','Journal':'Synthetic Journal'})
        leafcol='1.2 Agricultural System'
        value=next((key for key,ids in self.contract['leaf_columns'][leafcol]['values'].items() if len(ids)==1),None)
        self.assertIsNotNone(value)
        row[leafcol]=value
        records=app.make_records([row],self.contract)
        self.assertEqual(records[0]['crops'],['Rice','Wheat'])
        self.assertEqual(records[0]['journal'],'Synthetic Journal')
        self.assertEqual(records[0]['source'],'')  # Journal is not bibliographic source
        self.assertIn('theme1',records[0]['theme_node_ids'])
        self.assertTrue(records[0]['theme_paths'])
        row[leafcol]='999. Invented category'
        with self.assertRaisesRegex(ValueError,'Unapproved thematic code'):
            app.make_records([row],self.contract)

    def test_carry_enrichment_without_overriding_source(self):
        latest=[{'Filenames':'a.pdf','Title':'New title'}]
        previous=[{'Filenames':'a.pdf','Title':'Old title','lens_authors':'Researcher A',
                  'lens_match_status':'EXACT_DOI_MATCH'}]
        count=app.carry_forward_bibliography(latest,previous,self.contract)
        self.assertEqual(latest[0]['Title'],'New title')
        self.assertEqual(latest[0]['lens_authors'],'Researcher A')
        self.assertEqual(count,2)

    def test_full_current_csv_golden_counts_when_provided(self):
        import os
        fixture=os.environ.get('CGIAR_BASELINE_CSV')
        if not fixture:self.skipTest('Private baseline CSV not present; set CGIAR_BASELINE_CSV')
        rows=app.load_csv(Path(fixture))
        records=app.make_records(rows,self.contract)
        self.assertEqual(len(records),2652)
        self.assertEqual(sum(not r['countries'] for r in records),476)
        tree=app.make_tree(records,self.contract)
        self.assertEqual({t['id']:t['count'] for t in tree['themes']},
                         {'theme1':1041,'theme2':386,'theme3':1142,'theme4':502,'theme5':667})
        summary_products=set(name for row in rows for name in app.parse_names(row['Crop/livestock/tree/fish name (CLEAN)']))
        self.assertEqual(len(summary_products),274)

if __name__=='__main__':unittest.main()