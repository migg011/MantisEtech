-- Preserva datas de fabricação parciais como texto no banco anterior.
-- Compatibilidade: o banco novo usa manage.py migrate; estes scripts são utilizados por adopt_legacy.
-- Registro opcional da data de fabricação, inclusive ano isolado ou mês/ano.
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS manufacturing_date_text VARCHAR(10);
