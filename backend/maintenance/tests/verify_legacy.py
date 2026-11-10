"""Valida adoção usando exclusivamente um PostgreSQL vazio indicado por DATABASE_URL.

Execute: python maintenance/tests/verify_legacy.py
O script deixa os dados fictícios no banco informado para inspeção.
"""
import os
from pathlib import Path
import subprocess
import sys

import bcrypt
import psycopg

root = Path(__file__).resolve().parents[2]
url = os.environ['DATABASE_URL']
password = 'Legacy-validation-password-2026'
legacy_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
with psycopg.connect(url) as db:
    with db.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        if cursor.fetchone()[0]:
            raise RuntimeError('Use only an empty database dedicated to this validation.')
        for path in sorted((root / 'maintenance' / 'legacy_sql').glob('*.sql')):
            cursor.execute(path.read_text(encoding='utf-8'))
        cursor.execute("INSERT INTO sectors(code,name) VALUES('LEGACY','Setor preservado') RETURNING id")
        sector = cursor.fetchone()[0]
        cursor.execute("INSERT INTO lines(code,name,sector_id) VALUES('LEGACY','Linha preservada',%s) RETURNING id", [sector])
        line = cursor.fetchone()[0]
        cursor.execute("INSERT INTO users(name,registration,password_hash,role) VALUES('Admin preservado','LEGACY',%s,'ADMINISTRADOR') RETURNING id", [legacy_hash])
        user = cursor.fetchone()[0]
        cursor.execute("INSERT INTO equipment(equipment_type_id,sector_id,line_id,position,serial) VALUES(1,%s,%s,1,'SERIE-ORIGINAL') RETURNING id", [sector, line])
        equipment = cursor.fetchone()[0]
        cursor.execute("INSERT INTO work_orders(equipment_id,opened_by,problem) VALUES(%s,%s,'Falha preservada')", [equipment, user])
        cursor.execute("INSERT INTO equipment_attachments(equipment_id,kind,filename,mime_type,content,size_bytes,uploaded_by) VALUES(%s,'MANUAL','original.pdf','application/pdf',%s,9,%s)", [equipment, b'%PDF-test', user])

subprocess.run([sys.executable, 'manage.py', 'adopt_legacy'], cwd=root, check=True)
# Uma segunda execução verifica idempotência.
subprocess.run([sys.executable, 'manage.py', 'adopt_legacy'], cwd=root, check=True)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, str(root))
import django
django.setup()
from django.contrib.auth import authenticate
from maintenance.models import Equipment, EquipmentAttachment, WorkOrder, User
assert Equipment.objects.get(pk=equipment).serial == 'SERIE-ORIGINAL'
assert bytes(EquipmentAttachment.objects.get(equipment_id=equipment).content) == b'%PDF-test'
assert WorkOrder.objects.get().problem == 'Falha preservada'
assert authenticate(username='LEGACY', password=password) is not None
assert not User.objects.get(pk=user).password.startswith('$2')
print('Legacy adoption validated: registrations, orders, binary attachment, and bcrypt login preserved; command is idempotent.')
