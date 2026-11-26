# -*- coding: utf-8 -*-
import base64
import io
import openpyxl
from datetime import date, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestDailyLogImportExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Find or create warehouse & farm location
        cls.warehouse = cls.env['stock.warehouse'].search([], limit=1)
        cls.location_stock = cls.warehouse.lot_stock_id if cls.warehouse else cls.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
        cls.farm = cls.env['taghini.farm'].search([], limit=1)
        if not cls.farm:
            cls.farm = cls.env['taghini.farm'].create({
                'name': 'Test Main Farm',
                'warehouse_id': cls.warehouse.id if cls.warehouse else False,
            })

        # Pen
        cls.pen = cls.env['taghini.pen'].search([('farm_id', '=', cls.farm.id)], limit=1)
        if not cls.pen:
            cls.pen = cls.env['taghini.pen'].create({
                'name': 'Pen 101 Test',
                'farm_id': cls.farm.id,
                'capacity': 5000,
            })

        # Bird Product & Template
        cls.bird_product = cls.env['product.product'].search([('name', 'ilike', 'Broiler')], limit=1)
        if not cls.bird_product:
            cls.bird_product = cls.env['product.product'].create({
                'name': 'Test Broiler Bird',
                'type': 'consu',
            })
        cls.bird_template = cls.bird_product.product_tmpl_id

        # Breeder Standard
        cls.breeder_standard = cls.env['taghini.farm.standard'].search([('standard_type', '=', 'breeder')], limit=1)
        if not cls.breeder_standard:
            cls.breeder_standard = cls.env['taghini.farm.standard'].create({
                'name': 'Test Breeder Std',
                'standard_type': 'breeder',
            })

        # Supplier & Mother Batch
        cls.supplier = cls.env['res.partner'].search([], limit=1)
        if not cls.supplier:
            cls.supplier = cls.env['res.partner'].create({'name': 'Test Supplier'})

        cls.batch = cls.env['taghini.chicken.batch'].create({
            'name': 'BATCH-TEST-001',
            'supplier_id': cls.supplier.id,
            'total_quantity': 5000,
            'date': date.today() - timedelta(days=10),
        })

        # Standard
        cls.standard = cls.env['taghini.farm.standard'].search([], limit=1)
        if not cls.standard:
            cls.standard = cls.env['taghini.farm.standard'].create({
                'name': 'Ross 308 Standard Test',
                'breed': 'Ross 308',
            })

        # Test Flock
        cls.flock = cls.env['taghini.flock'].create({
            'name': 'FLOCK-TEST-IMPORT-EXPORT-001',
            'batch_id': cls.batch.id,
            'standard_id': cls.standard.id,
            'quantity_placed': 2000,
            'pen_model_id': cls.pen.id,
            'product_id': cls.bird_product.id,
            'initial_birds': 2000,
            'start_date': date.today() - timedelta(days=10),
            'state': 'active',
        })

        # Test Standard Remark
        cls.remark = cls.env['taghini.farm.remark'].search([('name', 'ilike', 'Normal')], limit=1)
        if not cls.remark:
            cls.remark = cls.env['taghini.farm.remark'].create({
                'name': 'Normal Activity',
                'category': 'normal',
                'need_escalation': False,
            })

        # Test Medication Product
        cls.med_product = cls.env['product.product'].search([('name', 'ilike', 'Vitamin')], limit=1)
        if not cls.med_product:
            cls.med_product = cls.env['product.product'].create({
                'name': 'Test Vitamin Booster',
                'type': 'consu',
                'purchase_ok': True,
            })

    def test_01_download_template_xlsx(self):
        """Verify downloading the Excel template generates valid workbook with instructions."""
        wizard = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'template',
            'template_format': 'xlsx',
            'template_flock_id': self.flock.id,
        })
        res = wizard.action_download_template()
        self.assertEqual(res['type'], 'ir.actions.act_url')
        self.assertTrue(wizard.file_output)
        self.assertTrue(wizard.file_name.endswith('.xlsx'))

        # Read back workbook
        file_bytes = base64.b64decode(wizard.file_output)
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
        self.assertIn("Daily Logs", wb.sheetnames)
        self.assertIn("Instructions & Field Guide", wb.sheetnames)

        ws = wb["Daily Logs"]
        headers = [ws.cell(row=1, column=c).value for c in range(1, 18)]
        self.assertIn("Date", headers)
        self.assertIn("Flock", headers)
        self.assertIn("Mortality", headers)
        self.assertIn("Feed Bags", headers)

    def test_02_download_template_csv(self):
        """Verify downloading the CSV template produces valid headers."""
        wizard = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'template',
            'template_format': 'csv',
            'template_flock_id': self.flock.id,
        })
        wizard.action_download_template()
        self.assertTrue(wizard.file_output)
        self.assertTrue(wizard.file_name.endswith('.csv'))

        csv_text = base64.b64decode(wizard.file_output).decode('utf-8-sig')
        self.assertIn("Date,Flock,Mortality,Feed Bags", csv_text)

    def test_03_export_daily_logs_xlsx_and_csv(self):
        """Create sample log records and verify export contains accurate flock data."""
        log1 = self.env['taghini.daily.log'].create({
            'flock_id': self.flock.id,
            'date': date.today() - timedelta(days=2),
            'mortality': 3,
            'feed_consumed_bags': 6,
            'water_consumed': 220.0,
            'actual_avg_weight': 1420.0,
            'remark_ids': [(4, self.remark.id)],
            'remarks': 'Day 8 regular checkup',
        })
        log2 = self.env['taghini.daily.log'].create({
            'flock_id': self.flock.id,
            'date': date.today() - timedelta(days=1),
            'mortality': 1,
            'feed_consumed_bags': 7,
            'water_consumed': 240.0,
            'actual_avg_weight': 1480.0,
        })

        # Test XLSX Export
        wizard_xlsx = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'export',
            'flock_id': self.flock.id,
            'export_format': 'xlsx',
        })
        wizard_xlsx.action_export()
        self.assertTrue(wizard_xlsx.file_output)
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(wizard_xlsx.file_output)))
        ws = wb.active
        self.assertEqual(ws.title, "Daily Operations Logs")

        # Find row containing self.flock.name
        found_flock = False
        for row in ws.iter_rows(values_only=True):
            if self.flock.name in [str(c) for c in row if c]:
                found_flock = True
                break
        self.assertTrue(found_flock, "Exported XLSX should contain the flock name")

        # Test CSV Export
        wizard_csv = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'export',
            'flock_id': self.flock.id,
            'export_format': 'csv',
        })
        wizard_csv.action_export()
        self.assertTrue(wizard_csv.file_output)
        csv_text = base64.b64decode(wizard_csv.file_output).decode('utf-8-sig')
        self.assertIn(self.flock.name, csv_text)

    def test_04_import_daily_logs_csv(self):
        """Verify importing logs from CSV creates records and computes flock statistics."""
        target_date1 = str(date.today() - timedelta(days=5))
        target_date2 = str(date.today() - timedelta(days=4))

        csv_content = (
            f"Date,Flock,Mortality,Feed Bags,Water (L),Actual Avg Weight (g),Remarks,Notes\n"
            f"{target_date1},{self.flock.name},4,10,380.0,1520.0,{self.remark.name},Imported row 1\n"
            f"{target_date2},{self.flock.name},2,11,400.0,1570.0,{self.remark.name},Imported row 2\n"
        )

        wizard = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'import',
            'import_file': base64.b64encode(csv_content.encode('utf-8')),
            'import_filename': 'test_import.csv',
            'target_flock_id': self.flock.id,
            'on_existing': 'update',
        })
        wizard.action_import()

        self.assertEqual(wizard.step, 'result')
        self.assertIn("Records Created: 2", wizard.result_summary)

        # Verify logs in DB
        log1 = self.env['taghini.daily.log'].search([
            ('flock_id', '=', self.flock.id),
            ('date', '=', target_date1),
        ])
        self.assertTrue(log1)
        self.assertEqual(log1.mortality, 4)
        self.assertEqual(log1.feed_consumed_bags, 10)
        self.assertEqual(log1.feed_consumed_g, 250000.0)
        self.assertEqual(log1.water_consumed, 380.0)
        self.assertEqual(log1.actual_avg_weight, 1520.0)
        self.assertIn(self.remark, log1.remark_ids)
        self.assertEqual(log1.remarks, 'Imported row 1')

    def test_05_import_duplicate_update_and_skip(self):
        """Verify on_existing='update' modifies values and on_existing='skip' ignores existing dates."""
        target_date = str(date.today() - timedelta(days=3))

        # First import
        csv_1 = f"Date,Flock,Mortality,Feed Bags\n{target_date},{self.flock.name},5,8\n"
        w1 = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'import',
            'import_file': base64.b64encode(csv_1.encode('utf-8')),
            'import_filename': 'initial.csv',
            'on_existing': 'update',
        })
        w1.action_import()

        log = self.env['taghini.daily.log'].search([
            ('flock_id', '=', self.flock.id),
            ('date', '=', target_date),
        ])
        self.assertEqual(log.mortality, 5)

        # Update import
        csv_update = f"Date,Flock,Mortality,Feed Bags\n{target_date},{self.flock.name},9,12\n"
        w2 = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'import',
            'import_file': base64.b64encode(csv_update.encode('utf-8')),
            'import_filename': 'update.csv',
            'on_existing': 'update',
        })
        w2.action_import()
        log.invalidate_recordset()
        self.assertEqual(log.mortality, 9)
        self.assertEqual(log.feed_consumed_bags, 12)

        # Skip import
        csv_skip = f"Date,Flock,Mortality,Feed Bags\n{target_date},{self.flock.name},1,2\n"
        w3 = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'import',
            'import_file': base64.b64encode(csv_skip.encode('utf-8')),
            'import_filename': 'skip.csv',
            'on_existing': 'skip',
        })
        w3.action_import()
        log.invalidate_recordset()
        self.assertEqual(log.mortality, 9, "Value should remain unchanged when on_existing='skip'")

    def test_06_import_error_diagnostics(self):
        """Verify invalid date and unknown flock report detailed diagnostics without crashing."""
        csv_bad = (
            "Date,Flock,Mortality\n"
            "INVALID_DATE,UNKNOWN_FLOCK_999,5\n"
        )
        wizard = self.env['taghini.daily.log.import.export.wizard'].create({
            'mode': 'import',
            'import_file': base64.b64encode(csv_bad.encode('utf-8')),
            'import_filename': 'bad.csv',
        })
        wizard.action_import()
        self.assertEqual(wizard.step, 'result')
        self.assertIn("Errors / Warnings: 1", wizard.result_summary)
        self.assertTrue(wizard.error_details)
        self.assertIn("Missing or invalid Date", wizard.error_details)

    def test_07_unique_sequence_generation(self):
        """Verify unique sequence-generated IDs on Flocks, Daily Logs, Pens, Farms, and Breeder Logs."""
        # 1. Flock sequence
        new_flock = self.env['taghini.flock'].create({
            'batch_id': self.batch.id,
            'standard_id': self.standard.id,
            'pen_model_id': self.pen.id,
            'quantity_placed': 1000,
            'product_id': self.bird_product.id,
            'initial_birds': 1000,
            'start_date': date.today(),
            'state': 'draft',
        })
        self.assertTrue(new_flock.flock_code)
        self.assertNotEqual(new_flock.flock_code, 'New')
        self.assertTrue(new_flock.flock_code.startswith('FLK/'))

        # 2. Daily Log sequence
        new_log = self.env['taghini.daily.log'].create({
            'flock_id': new_flock.id,
            'date': date.today(),
            'mortality': 1,
            'feed_consumed_bags': 2,
        })
        self.assertTrue(new_log.name)
        self.assertNotEqual(new_log.name, 'New')
        self.assertTrue(new_log.name.startswith('LOG/'))

        # 3. Pen sequence
        new_pen = self.env['taghini.pen'].create({
            'name': 'Pen Beta Test',
            'farm_id': self.farm.id,
            'location_id': self.location_stock.id,
            'capacity': 3000,
        })
        self.assertTrue(new_pen.pen_code)
        self.assertNotEqual(new_pen.pen_code, 'New')
        self.assertTrue(new_pen.pen_code.startswith('PEN/'))

        # 4. Farm sequence
        new_farm = self.env['taghini.farm'].create({
            'name': 'Site Gamma Test',
            'warehouse_id': self.warehouse.id if self.warehouse else False,
        })
        self.assertTrue(new_farm.code)
        self.assertNotEqual(new_farm.code, 'New')
        self.assertTrue(new_farm.code.startswith('FRM/'))

        # 5. Breeder Pen Daily Log sequence
        breeder_batch = self.env['taghini.breeder.batch'].create({
            'name': 'BRD-TEST-001',
            'source_partner_id': self.supplier.id,
            'female_order_qty': 100,
            'bird_variant_id': self.bird_template.id,
            'standard_id': self.breeder_standard.id,
        })
        pen = self.env['taghini.pen'].create({
            'name': 'Test Pen BRD',
            'farm_id': new_farm.id,
            'location_id': self.location_stock.id,
        })
        flock = self.env['taghini.breeder.flock'].create({
            'batch_id': breeder_batch.id,
            'pen_id': pen.id,
            'initial_females': 50,
            'initial_males': 6,
        })
        flock.action_activate()
        new_blog = self.env['taghini.breeder.pen.log'].create({
            'flock_id': flock.id,
            'date': date.today(),
            'female_mortality': 1,
        })
        self.assertTrue(new_blog.name)
        self.assertNotEqual(new_blog.name, 'New')
        self.assertTrue(new_blog.name.startswith('BPLOG/'))

    def test_pen_capacity_validation(self):
        """Test pen capacity enforcement during breeder flock allocation"""
        from odoo.exceptions import ValidationError
        farm = self.env['taghini.farm'].search([], limit=1)
        pen_cap = self.env['taghini.pen'].create({
            'name': 'Pen Capacity Test',
            'farm_id': farm.id,
            'location_id': self.location_stock.id,
            'capacity': 1000,
        })
        self.assertEqual(pen_cap.capacity, 1000)

        batch = self.env['taghini.breeder.batch'].create({
            'name': 'BATCH-CAP-TEST',
            'source_partner_id': self.supplier.id,
            'female_order_qty': 2000,
            'male_order_qty': 300,
            'bird_variant_id': self.bird_template.id,
            'standard_id': self.breeder_standard.id,
        })

        # Allocating within capacity (800 females + 100 males = 900 <= 1000) succeeds
        valid_flock = self.env['taghini.breeder.flock'].create({
            'batch_id': batch.id,
            'pen_id': pen_cap.id,
            'initial_females': 800,
            'initial_males': 100,
        })
        self.assertEqual(valid_flock.total_initial_placed, 900)

        # Allocating over capacity (950 females + 100 males = 1050 > 1000) raises ValidationError
        with self.assertRaises(ValidationError):
            valid_flock.write({
                'initial_females': 950,
                'initial_males': 100,
            })

    def test_breeder_egg_collection_visibility(self):
        """Test that egg collection tab is controlled by laying phase"""
        farm = self.env['taghini.farm'].search([], limit=1)
        pen = self.env['taghini.pen'].create({
            'name': 'Pen Egg Vis Test',
            'farm_id': farm.id,
            'location_id': self.location_stock.id,
            'capacity': 5000,
        })
        batch = self.env['taghini.breeder.batch'].create({
            'name': 'BATCH-EGG-TEST',
            'source_partner_id': self.supplier.id,
            'female_order_qty': 1000,
            'male_order_qty': 150,
            'bird_variant_id': self.bird_template.id,
            'standard_id': self.breeder_standard.id,
        })
        # Young flock (e.g. brooding/rearing, placed today)
        flock = self.env['taghini.breeder.flock'].create({
            'batch_id': batch.id,
            'pen_id': pen.id,
            'initial_females': 500,
            'initial_males': 60,
            'start_date': date.today(),
        })
        flock.action_activate()

        # Rearing daily log: is_laying should be False
        rearing_log = self.env['taghini.breeder.pen.log'].create({
            'flock_id': flock.id,
            'date': date.today(),
        })
        self.assertEqual(rearing_log.phase, 'brooding')
        self.assertFalse(rearing_log.is_laying, "Egg tab should be hidden during brooding/rearing")

        # Flock reaching laying phase automatically reveals egg tab
        flock.laying_started = True
        rearing_log._compute_is_laying()
        self.assertTrue(rearing_log.is_laying, "Egg tab should be visible once flock starts laying")
