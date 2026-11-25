# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestBreederBatchState(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.partner = cls.env.company.partner_id
        cls.farm = cls.env['taghini.farm'].create({
            'name': 'Test Breeder Farm',
            'farm_type': 'breeder',
            'company_id': cls.company.id,
            'warehouse_id': cls.warehouse.id,
        })
        cls.pen_loc_1 = cls.env['stock.location'].create({
            'name': 'Breeder Pen Loc 1',
            'usage': 'internal',
            'location_id': cls.warehouse.view_location_id.id,
            'company_id': cls.company.id,
        })
        cls.pen_loc_2 = cls.env['stock.location'].create({
            'name': 'Breeder Pen Loc 2',
            'usage': 'internal',
            'location_id': cls.warehouse.view_location_id.id,
            'company_id': cls.company.id,
        })
        cls.pen1 = cls.env['taghini.pen'].create({
            'name': 'Breeder Pen 1',
            'farm_id': cls.farm.id,
            'location_id': cls.pen_loc_1.id,
        })
        cls.pen2 = cls.env['taghini.pen'].create({
            'name': 'Breeder Pen 2',
            'farm_id': cls.farm.id,
            'location_id': cls.pen_loc_2.id,
        })
        cls.bird_product = cls.env['product.template'].create({
            'name': 'Parent Stock Test Bird',
            'type': 'consu',
            'is_storable': True,
            'bird_variant': True,
        })
        cls.standard = cls.env['taghini.farm.standard'].create({
            'name': 'Test Breeder Standard',
            'standard_type': 'breeder',
        })

    def _create_batch(self, females=100, males=15):
        return self.env['taghini.breeder.batch'].create({
            'source_partner_id': self.partner.id,
            'farm_id': self.farm.id,
            'bird_variant_id': self.bird_product.id,
            'standard_id': self.standard.id,
            'female_order_qty': females,
            'male_order_qty': males,
            'shipped_female_qty': females,
            'shipped_male_qty': males,
        })

    def test_01_received_and_auto_sorted(self):
        batch = self._create_batch(females=0, males=0)
        with self.assertRaises(UserError):
            batch.action_mark_received()

        batch.write({'shipped_female_qty': 100, 'shipped_male_qty': 15})
        batch.action_mark_received()
        self.assertEqual(batch.state, 'received')

        # Partial allocation blocks action_mark_sorted
        flock1 = self.env['taghini.breeder.flock'].create({
            'batch_id': batch.id,
            'pen_id': self.pen1.id,
            'initial_females': 60,
            'initial_males': 10,
        })
        with self.assertRaises(UserError):
            batch.action_mark_sorted()

        # Completing remaining allocation auto-advances to 'sorted'
        self.env['taghini.breeder.flock'].create({
            'batch_id': batch.id,
            'pen_id': self.pen2.id,
            'initial_females': 40,
            'initial_males': 5,
        })
        self.assertEqual(batch.state, 'sorted')
        self.assertTrue(flock1.exists())

    def test_02_mating_laying_close_cancel_validations(self):
        batch = self._create_batch(females=100, males=15)
        batch.action_mark_received()
        flock1 = self.env['taghini.breeder.flock'].create({
            'batch_id': batch.id,
            'pen_id': self.pen1.id,
            'initial_females': 100,
            'initial_males': 15,
            'start_date': fields.Date.today(),
        })
        self.assertEqual(batch.state, 'sorted')

        # Cannot move to mating while pen is still draft
        with self.assertRaises(UserError):
            batch.action_mark_mating()

        flock1.action_activate()
        batch.action_mark_mating()
        self.assertEqual(batch.state, 'mating')

        # Cannot cancel while active pen exists
        with self.assertRaises(UserError):
            batch.action_cancel_batch()

        # Cannot move to laying while pen is in brooding/rearing
        with self.assertRaises(UserError):
            batch.action_mark_laying()

        # Toggling laying_started auto-advances mating -> laying
        flock1.write({'laying_started': True})
        self.assertEqual(batch.state, 'laying')

        # Cannot close batch while pen is still active
        with self.assertRaises(UserError):
            batch.action_close_batch()

        # Moving start_date to 30 weeks ago also sets lifecycle_phase='lay'
        flock1.write({'start_date': fields.Date.today() - timedelta(weeks=30)})
        self.assertEqual(flock1.lifecycle_phase, 'lay')
