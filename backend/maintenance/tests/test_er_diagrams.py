"""Cardinalities must reflect the actual FK, nullability, and uniqueness in PostgreSQL."""
from django.test import SimpleTestCase

from maintenance.er_diagrams import mermaid, read_relations


class ErCardinalitiesTests(SimpleTestCase):
    def table(self, name, columns, constraints):
        return {'name': name, 'module': 'Negócio',
                'columns': [{'name': column_name, 'nullable': nullable, 'pg_type': 'int8'}
                            for column_name, nullable in columns],
                'constraints': [{'name': f'c{i}', 'kind': kind, 'definition': definition,
                                 'target': 'parents' if kind == 'f' else None}
                                for i, (kind, definition) in enumerate(constraints)]}

    def test_optional_fk_and_composite_key_stay_one_to_many(self):
        parent = self.table('parents', [('id', False)], [('p', 'PRIMARY KEY (id)')])
        child = self.table('children', [('parent_id', True), ('other_id', False)],
                           [('p', 'PRIMARY KEY (parent_id, other_id)'),
                            ('f', 'FOREIGN KEY (parent_id) REFERENCES parents(id)')])
        tables, relations = read_relations({'tables': [parent, child]})
        self.assertTrue(relations[0]['optional'])
        self.assertFalse(relations[0]['unique'])
        self.assertIn('parents |o--o{ children', mermaid(tables, relations, ['parents', 'children']))

    def test_pk_that_is_also_fk_is_one_to_one(self):
        parent = self.table('parents', [('id', False)], [('p', 'PRIMARY KEY (id)')])
        sheet = self.table('sheets', [('parent_id', False)],
                           [('p', 'PRIMARY KEY (parent_id)'),
                            ('f', 'FOREIGN KEY (parent_id) REFERENCES parents(id)')])
        tables, relations = read_relations({'tables': [parent, sheet]})
        self.assertTrue(relations[0]['unique'])
        self.assertFalse(relations[0]['optional'])
        text = mermaid(tables, relations, ['parents', 'sheets'])
        self.assertIn('int8 parent_id PK, FK', text)
        self.assertIn('parents ||--o| sheets', text)
