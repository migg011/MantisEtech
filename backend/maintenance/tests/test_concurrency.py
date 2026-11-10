"""Teste transacional PostgreSQL: duas execuções disputam a mesma posição para conferir os bloqueios da montagem."""

from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from maintenance.services import registrations
from maintenance.models import User, Sector, Line, EquipmentType, Equipment, EquipmentMovement
from maintenance.models import EquipmentPreventive, PreventiveExecution, PreventiveChecklist
from maintenance.authentication import issue_token
from django.test import Client
from django.utils import timezone
@skipUnless(connection.vendor == 'postgresql', 'Concurrent locking requires PostgreSQL.')
class AllocationConcurrencyTests(TransactionTestCase):
    """Executa concorrência real com transações e conexões independentes no PostgreSQL."""
    def test_transfer_and_allocation_cannot_both_succeed(self):
        """Disputa pela mesma máquina não deixa alocação em uma linha de outro setor."""
        sector = Sector.objects.create(code='origem-transferencia', name='Origem')
        destination = Sector.objects.create(code='destino-transferencia', name='Destino')
        line = Line.objects.create(code='linha-transferencia', name='Linha', sector=sector)
        kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name':'Máquina'})
        actor = User.objects.create_user('transfer-race', 'Strong-Test-Password-123', name='Admin', role='ADMINISTRADOR')
        machine = Equipment.objects.create(equipment_type=kind, sector=sector)
        def attempt(transfer):
            close_old_connections()
            try:
                if transfer:
                    registrations.transfer_equipment(machine.pk, sector.pk, destination.pk, 'Teste concorrente', actor)
                else:
                    registrations.allocate_equipment(line.pk, machine.pk, 1, actor)
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [True, False]))
        self.assertEqual(sorted(results), [False, True])
        machine.refresh_from_db()
        if machine.line_id:
            self.assertEqual(machine.sector_id, line.sector_id)
        else:
            self.assertEqual(machine.sector_id, destination.pk)
        self.assertEqual(machine.movements.count(), 1)

    def test_two_allocations_cannot_occupy_same_position(self):
        """Duas transações simultâneas não ocupam a mesma posição da linha."""
        sector = Sector.objects.create(code='SET-race', name='SMT')
        line = Line.objects.create(code='LIN-race', name='Linha concorrente', sector=sector)
        kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name': 'PICK & PLACE'})
        actor = User.objects.create_user('race', 'Strong-Test-Password-123', name='Admin', role='ADMINISTRADOR')
        equipment = [Equipment.objects.create(equipment_type=kind, sector=sector) for _ in range(2)]
        def attempt(pk):
            """Abre uma conexão por execução concorrente, tenta alocar e fecha a conexão ao terminar."""
            close_old_connections()
            try:
                registrations.allocate_equipment(line.pk, pk, 1, actor)
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [item.pk for item in equipment]))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(EquipmentMovement.objects.count(), 1)


@skipUnless(connection.vendor == 'postgresql', 'Concurrent locking requires PostgreSQL.')
class PreventiveConcurrencyTests(TransactionTestCase):
    """Testa bloqueios reais do PostgreSQL com duas conexões independentes; SQLite não comprova esse comportamento."""
    def test_two_completions_do_not_duplicate_execution(self):
        """Duas requisições tentam concluir a mesma OS com a mesma revisão. Espera uma confirmação, um conflito HTTP 409 e apenas um registro de execução."""
        kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name': 'Tipo'})
        machine = Equipment.objects.create(equipment_type=kind)
        actor = User.objects.create_user('prev-race', 'Strong-Test-Password-123', name='Técnico', role='TECNICO')
        today = timezone.localdate()
        schedule = EquipmentPreventive.objects.create(equipment=machine, frequency='MENSAL', next_due=today)
        token = issue_token(actor)
        PreventiveChecklist.objects.create(equipment_type=kind, frequency='MENSAL', items=['Verificar sensores'])
        order = Client(HTTP_AUTHORIZATION='Bearer ' + token).post('/api/preventive-orders', {
            'scheduleId':schedule.pk, 'expectedDueDate':today.isoformat(), 'plannedDate':today.isoformat(), 'assignedToId':actor.pk
        }, content_type='application/json').json()

        def attempt(_):
            """Abre uma conexão própria, envia a conclusão autenticada e retorna o status HTTP. Fecha a conexão ao terminar para isolar as duas tentativas."""
            close_old_connections()
            try:
                client = Client(HTTP_AUTHORIZATION='Bearer ' + token)
                response = client.post(f"/api/preventive-orders/{order['id']}/complete", {
                    'performedDate': today.isoformat(), 'revision':order['revision'], 'results':[{'status':'REALIZADO'}]
                }, content_type='application/json')
                return response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(PreventiveExecution.objects.count(), 1)
