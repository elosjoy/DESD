"""
Management command: calculate_settlements

Usage:
    python manage.py calculate_settlements                    # Calculate for current week
    python manage.py calculate_settlements --week 0          # Calculate for current week
    python manage.py calculate_settlements --week -1         # Calculate for last week
    python manage.py calculate_settlements --producer 5      # Calculate for specific producer (current week)

This command is typically run weekly via a cron job or scheduler.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from marketplace.models import ProducerProfile
from marketplace.services.settlement_service import (
    calculate_settlement_for_producer,
    calculate_settlements_for_week,
    get_week_boundaries,
)


class Command(BaseCommand):
    help = 'Calculate settlements for producers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week',
            type=int,
            default=0,
            help='Week offset from today (0=current, -1=last week, etc.)',
        )
        parser.add_argument(
            '--producer',
            type=int,
            help='Calculate for specific producer ID (optional)',
        )

    def handle(self, *args, **options):
        week_offset = options.get('week', 0)
        producer_id = options.get('producer')

        # Calculate the target week
        today = timezone.now().date()
        target_date = today + timedelta(weeks=week_offset)
        week_start, week_end = get_week_boundaries(target_date)

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCalculating settlements for week {week_start} to {week_end}'
            )
        )

        try:
            if producer_id:
                # Calculate for single producer
                producer = ProducerProfile.objects.get(id=producer_id)
                settlement = calculate_settlement_for_producer(
                    producer,
                    week_start=week_start,
                    week_end=week_end,
                )
                self._print_settlement(settlement)

            else:
                # Calculate for all producers with orders
                settlements = calculate_settlements_for_week(
                    week_start=week_start,
                    week_end=week_end,
                )

                if not settlements:
                    self.stdout.write(
                        self.style.WARNING(
                            'No settlements created (no delivered items found)'
                        )
                    )
                    return

                self.stdout.write(
                    self.style.SUCCESS(f'\n✓ Created/updated {len(settlements)} settlements\n')
                )

                total_marketplace_commission = sum(s.commission_amount for s in settlements)
                total_producer_payouts = sum(s.net_payout for s in settlements)
                total_sales = sum(s.total_order_value for s in settlements)

                for settlement in settlements:
                    self._print_settlement(settlement)

                self.stdout.write(
                    self.style.SUCCESS('\n' + '=' * 70)
                )
                self.stdout.write(
                    f'Total Sales:            £{total_sales:.2f}'
                )
                self.stdout.write(
                    f'Marketplace Commission: £{total_marketplace_commission:.2f}'
                )
                self.stdout.write(
                    f'Producer Payouts:       £{total_producer_payouts:.2f}'
                )
                self.stdout.write(
                    self.style.SUCCESS('=' * 70 + '\n')
                )

        except ProducerProfile.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Producer with ID {producer_id} not found')
            )

    def _print_settlement(self, settlement):
        """Helper to print a single settlement."""
        self.stdout.write(
            f'{settlement.producer.producer_name:30} | '
            f'Sales: £{settlement.total_order_value:10.2f} | '
            f'Commission: £{settlement.commission_amount:8.2f} ({settlement.commission_rate}%) | '
            f'Payout: £{settlement.net_payout:10.2f}'
        )
