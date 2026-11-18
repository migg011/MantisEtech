"""Preenche um banco vazio com exemplos fictícios para a apresentação."""

from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from maintenance.models import (
    Equipment, EquipmentPreventive, EquipmentType, Feeder, FeederMaintenance,
    Line, PreventiveExecution, PreventiveOrder, Sector, User,
)
from maintenance.preventive_planning import planning_lock, reserve_next_shift
from maintenance.schedule_rules import next_due_value


class Command(BaseCommand):
    help = 'Cria os cadastros e o histórico fictícios da demonstração.'

    @transaction.atomic
    def handle(self, *args, **options):
        planning_lock()
        if Sector.objects.exists() or Equipment.objects.exists() or Line.objects.exists():
            self.stdout.write('Já há cadastros no banco. Os dados de demonstração não foram inseridos.')
            return

        admin = User.objects.filter(role='ADMINISTRADOR', active=True).order_by('pk').first()
        if admin is None:
            raise CommandError('Crie um administrador antes de preparar a demonstração.')

        sector = Sector.objects.create(
            code='DEMO-SMT', name='Produção SMT · Demonstração',
            description='Setor fictício para apresentar o MANTIS.',
        )
        line = Line.objects.create(code='DEMO-SMT-01', name='Linha SMT 01', sector=sector)
        machines = [
            ('MAGAZINE LOADER', 'PCB Loader', 'Alimenta a linha com placas.'),
            ('PRINTER', 'DEK', 'Aplica pasta de solda sobre a placa.'),
            ('CONVEYOR', 'Conveyor', 'Transporta a placa entre as máquinas.'),
            ('SPI', 'SPI', 'Inspeciona a aplicação da pasta de solda.'),
            ('PICK & PLACE', 'NXT', 'Posiciona os componentes na placa.'),
            ('AOI', 'AOI', 'Inspeciona visualmente a montagem da placa.'),
        ]
        equipment_by_name = {}
        for position, (kind, name, description) in enumerate(machines, start=1):
            equipment_by_name[name] = Equipment.objects.create(
                equipment_type=EquipmentType.objects.get(name=kind),
                name=name, asset_number=f'DEMO-{position:03d}', sector=sector,
                line=line, position=position, description=description,
            )

        today = timezone.localdate()
        feeder = Feeder.objects.create(sector=sector, line=line, platform='NXT',
                                       part_number='DEMO-FDR-008', width='8 mm')
        FeederMaintenance.objects.create(
            feeder=feeder, date=today - timedelta(days=3),
            description='Registro simulado: inspeção visual e teste de avanço da fita.',
        )
        order = self.create_preventive_example(equipment_by_name['NXT'], admin, today)
        self.stdout.write(self.style.SUCCESS(f'Demonstração criada com a OS {order.number} concluída.'))

    def create_preventive_example(self, machine, admin, today):
        performed = today - timedelta(days=28)
        items = [
            'Registrar a inspeção visual do equipamento.',
            'Registrar a verificação do estado dos feeders.',
            'Registrar o resultado do teste de funcionamento.',
        ]
        notes = 'Execução fictícia para demonstrar o relatório de manutenção.'
        schedule = EquipmentPreventive.objects.create(
            equipment=machine, frequency='MENSAL', next_due=next_due_value(performed, 'MENSAL'),
            last_performed=performed, checklist_items=items,
        )
        schedule.next_due, schedule.planned_time = reserve_next_shift(schedule, max(today, schedule.next_due))
        schedule.save(update_fields=['next_due', 'planned_time'])

        # A OS guarda o retrato da máquina para o relatório continuar igual após edições.
        started_at = timezone.make_aware(datetime.combine(performed, time(6)))
        finished_at = started_at + timedelta(hours=1)
        order = PreventiveOrder.objects.create(
            schedule=schedule, status='CONCLUIDA', frequency=schedule.frequency,
            expected_due=performed, planned_date=performed, planned_time=time(6),
            equipment_snapshot={
                'name': machine.name, 'type_name': machine.equipment_type.name,
                'asset_number': machine.asset_number, 'sector_name': machine.sector.name,
                'line_name': machine.line.name,
            },
            items=items, results=[{'status': 'REALIZADO', 'notes': ''} for _ in items],
            safety_instructions='Exemplo fictício para apresentação. Consulte o procedimento aprovado para trabalhos reais.',
            notes=notes, performed_date=performed, performed_time=time(6),
            assigned_to=admin, assigned_name=admin.name, created_by=admin, created_at=started_at,
            finished_by=admin, executor_name=admin.name, finished_at=finished_at,
        )
        PreventiveExecution.objects.create(
            schedule=schedule, order=order, performed_date=performed, previous_due=performed,
            next_due=schedule.next_due, technician=admin, notes=notes, created_at=finished_at,
        )
        return order
