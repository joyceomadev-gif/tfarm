# Taghini Farm Management Module Guide Draft

This document is a working draft for a future user guide. It summarizes the module structure, options, actions, business flows, and practical testing scenarios for both commercial broiler operations and breeder stock operations.

## 1. Module Purpose

The module manages poultry operations across farm, daily operations, harvest, and abattoir production.

It currently supports two operational streams:

- Commercial broiler workflow
- Breeder stock workflow

The existing broiler flow is preserved. The breeder flow is added beside it with its own records, states, and daily tracking.

## 2. Main Functional Areas

- Farm pens and houses
- Purchased chicken batch allocation
- Broiler flock lifecycle
- Daily farm logs
- Growth standards and age-based feeding rules
- Harvest and abattoir processing
- Product classification for bird variants
- Breeder stock receiving and lifecycle tracking
- Dashboard and analysis views

## 3. Installed Models and What They Do

### 3.1 `taghini.pen`

File: `models/pen.py`

Purpose:

- Represents a pen, house, or unit in the farm.
- Links a pen to a company and stock location.
- Assigns a farm manager and veterinarian.
- Shows how many flocks are linked to the pen.

Main fields:

- `name`: Pen name.
- `company_id`: Farm branch or company.
- `location_id`: Stock location used by the pen.
- `manager_id`: Responsible farm manager.
- `vet_id`: Responsible vet.
- `flock_ids`: Related flocks.
- `series_count`: Computed count of flocks.

Main actions:

- `action_view_flocks()`: Opens flocks in the selected pen.
- `action_create_batch()`: Opens a new flock creation form for that pen.

### 3.2 `taghini.flock`

File: `models/flock.py`

Purpose:

- Main broiler production cycle record.
- Tracks one flock or batch from stocking to closure.
- Links source batch, pen, product, standard, daily logs, and harvests.

Main fields:

- `name`: Series or batch name.
- `start_date`: Stocking date.
- `batch_id`: Source chicken batch.
- `quantity_placed`: Number of birds placed.
- `pen_model_id`: Pen/house used.
- `company_id`: Related company from pen.
- `pen_id`: Physical stock location.
- `breed`: Breed name.
- `product_id`: Bird variant product.
- `initial_birds`: Stored initial stock.
- `current_birds`: Computed live birds remaining.
- `total_mortality`: Computed total dead birds.
- `mortality_rate`: Computed mortality percentage.
- `current_age`: Computed age in days.
- `log_ids`: Related daily logs.
- `standard_id`: Growth profile.
- `harvest_ids`: Related harvest records.
- `harvest_count`: Computed harvest count.
- `state`: Draft, active, closed, or cancelled.

Main computed logic:

- `_compute_age()`: Calculates current age from stocking date.
- `_compute_metrics()`: Calculates mortality totals and mortality rate.
- `_compute_current_birds()`: Computes live birds remaining after mortality and harvest.
- `_compute_harvest_count()`: Counts harvest records.

Main actions:

- `action_escalate_issue()`: Notifies vet and manager, posts chatter message, schedules activity.
- `action_add_daily_log()`: Opens the daily log popup form.
- `action_view_harvests()`: Opens harvest records.
- `action_start_batch()`: Moves state from draft to active.
- `action_close_batch()`: Closes the flock.
- `action_cancel_batch()`: Cancels the flock.
- `action_set_draft()`: Returns flock to draft.

Main constraint:

- `_check_pen_availability()`: Prevents multiple active series in the same pen.
- `_check_batch_quantity()`: Prevents invalid batch quantity allocation.

### 3.3 `taghini.daily.log`

File: `models/daily_log.py`

Purpose:

- Stores daily operational records for a flock.
- Covers mortality, feed, weight, health, harvest, and now farm activities.
- Posts stock moves for feed and medication.
- Creates scrap records for mortality.

Main fields:

- `flock_id`: Related flock.
- `pen_id`: Related stock location.
- `standard_id`: Related growth standard.
- `company_id`: Related company.
- `date`: Log date.
- `age_day`: Computed age.
- `state`: Draft or posted.
- `birds_count`: Computed birds at start of day.
- `mortality`: Daily mortality.
- `scrap_id`: Created scrap record.
- `daily_mortality_percent`: Daily mortality percentage.
- `cumm_mortality`: Cumulative mortality.
- `cumm_mortality_percent`: Cumulative mortality percentage.
- `feed_product_id`: Recommended feed.
- `feed_consumed_bags`: Feed bags used.
- `feed_consumed_g`: Feed consumption in grams.
- `move_id`: Related feed stock move.
- `feed_per_bird_g`: Feed per bird.
- `expected_feed_g`: Expected feed from standard.
- `variance_feed_g`: Feed variance.
- `cumm_actual_feed_g`: Cumulative actual feed.
- `cumm_expected_feed_g`: Cumulative expected feed.
- `actual_avg_weight`: Measured average bird weight.
- `expected_avg_weight`: Expected weight.
- `variance_weight`: Weight variance.
- `light_hours`: Lighting hours.
- `light_period`: Lighting schedule.
- `water_consumed`: Water usage.
- `medication_product_id`: Medication product.
- `medication_qty`: Medication quantity.
- `medication_uom_id`: Medication unit.
- `medication_move_id`: Medication stock move.
- `vaccine_name`: Vaccine name.
- `remarks`: Free-text remarks.
- `harvested_qty`: Birds harvested in the log.
- `harvested_weight`: Harvest weight.
- `store_items_received`: New store receipt notes.
- `farm_observations`: New observation notes.
- `farm_activities`: New general farm activities notes.

Main computed logic:

- `_compute_age_day()`: Computes age at log date.
- `_on_date_change_set_standard()`: Auto-fills feed and medication from growth standard lines.
- `_compute_feed_g()`: Converts bags to grams.
- `_compute_expectations()`: Computes expected feed and weight based on standard line rules.
- `_compute_cumulative_stats()`: Computes cumulative mortality and feed across logs.
- `_compute_daily_metrics()`: Computes start-of-day birds, mortality percent, and feed per bird.

Main actions:

- `action_post_log()`: Posts mortality scraps and stock moves, then marks the record as done.

Main protection:

- `unlink()`: Prevents deletion of posted logs.

### 3.4 `taghini.farm.standard`

File: `models/standard.py`

Purpose:

- Defines a growth profile or standard for a breed.
- Stores location references used during harvest.
- Holds standard lines that describe age ranges and expected outputs.

Main fields:

- `name`: Standard name.
- `breed`: Breed name.
- `abattoir_location_id`: Destination stock location for abattoir transfers.
- `storage_location_id`: Destination storage/freezer location.
- `line_ids`: Related age rule lines.

### 3.5 `taghini.farm.standard.line`

File: `models/standard.py`

Purpose:

- Defines age-based feeding and performance rules.

Main fields:

- `standard_id`: Parent standard.
- `age_min`: Minimum age.
- `age_max`: Maximum age.
- `product_id`: Recommended feed.
- `expected_feed_g`: Expected grams per bird.
- `expected_weight_g`: Target body weight.
- `medication_id`: Recommended medication.
- `medication_qty`: Medication quantity.
- `medication_uom_id`: Medication unit of measure.

### 3.6 `taghini.harvest`

File: `models/harvest.py`

Purpose:

- Captures the transfer of birds from the flock to the abattoir.
- Computes harvest performance and updates daily logs and flock status.

Main fields:

- `name`: Harvest reference.
- `date`: Harvest date.
- `company_id`: Farm branch.
- `flock_id`: Source flock.
- `pen_id`: Related pen.
- `birds_received`: Birds received at abattoir.
- `total_live_weight`: Total live weight in kg.
- `avg_harvest_weight_g`: Computed average weight.
- `feather_condition`: QC condition.
- `visual_quality`: QC visual rating.
- `notes`: Free notes.
- `total_feed_consumed_kg`: Computed total feed used by flock.
- `total_meds_count`: Count of medication days.
- `fcr`: Feed conversion ratio.
- `state`: Draft, processing, or done.
- `move_id`: Related stock move.

Main computed logic:

- `_compute_avg_weight()`: Computes average harvest weight.
- `_compute_performance()`: Computes feed used, medication count, and FCR.

Main actions:

- `create()`: Auto-generates harvest sequence.
- `action_confirm_harvest()`: Creates stock moves, updates or creates daily log, and closes flock if depleted.

Main protection:

- `unlink()`: Prevents deleting completed harvests.

### 3.7 `taghini.abattoir.batch`

File: `models/abattoir.py`

Purpose:

- Represents daily production at the abattoir.
- Handles reception, slaughtering, production output, yield, and stock posting.

Main fields:

- `name`: Production batch reference.
- `date`: Production date.
- `company_id`: Company.
- `start_time`: Production start time.
- `end_time`: Production end time.
- `production_hours`: Computed duration.
- `harvest_id`: Source harvest.
- `pen_id`: Related pen.
- `batch_id`: Source chicken batch.
- `input_birds`: Birds sent.
- `input_weight_kg`: Live weight input.
- `line_ids`: Production output lines.
- `series_line_ids`: Whole series output lines.
- `parts_line_ids`: Chicken parts output lines.
- `cuts_line_ids`: Chicken cuts output lines.
- `residuals_line_ids`: Residual output lines.
- `total_output_qty`: Computed total birds processed.
- `total_output_weight_kg`: Computed total output weight.
- `yield_percentage`: Computed yield percentage.
- `processing_loss_kg`: Computed process loss.
- `manager_id`: Abattoir manager.
- `attendants_present_percent`: Attendance percent.
- `defects_count`: Defects count.
- `dirty_section_score`: Cleanliness score.
- `cold_room_score`: Cold room score.
- `state`: Draft, reception, slaughtering, production, done.
- `birds_arrived`: Intake bird count.
- `weight_arrived`: Intake weight.
- `average_weight_arrived`: Computed intake average weight.
- `condition_of_birds`: Intake condition.
- `mortality_arrived`: Mortality on arrival.
- `mortality_percentage`: Mortality percentage.
- `defected_birds`: Defected birds.
- `defected_percentage`: Defect percentage.
- `hanging_start_time`: Hanging start datetime.
- `hanging_end_time`: Hanging end datetime.
- `total_hanging_duration`: Computed hanging duration.
- `bleeding_time`: Bleeding duration.
- `scalding_time`: Scalding duration.
- `scalding_temp`: Scalding temperature.
- `evisceration_time`: Evisceration duration.
- `stunning_time`: Stunning duration.
- `stunning_voltage`: Stunning voltage.
- `chiller_exit_time`: Chiller exit time.
- `blast_locking_time`: Blast locking time.

Main computed logic:

- `_compute_duration()`: Computes production hours.
- `_compute_totals()`: Totals output quantities and yield.
- `_compute_verification_stats()`: Computes verification averages and percentages.
- `_compute_hanging_duration()`: Formats hanging duration.

Main actions:

- `action_start_reception()`: Moves to reception stage.
- `action_confirm_verification()`: Validates and moves to slaughtering.
- `action_confirm_slaughtering()`: Moves to production.
- `create()`: Generates abattoir sequence.
- `action_post_inventory()`: Posts stock movements for input and output products.

### 3.8 `taghini.abattoir.line`

File: `models/abattoir.py`

Purpose:

- Stores production output lines for the abattoir.

Main fields:

- `batch_id`: Parent production batch.
- `product_id`: Output product.
- `category_type`: Derived category from product template.
- `no_bags`: Bag count.
- `quantity`: Piece or bird count.
- `weight_kg`: Output weight.
- `avg_weight`: Computed average unit weight.

### 3.9 `product.template` extension

File: `models/product.py`

Purpose:

- Adds bird-specific metadata to the normal product model so the rest of the system can still use product records in stock moves, purchase orders, and inventory.

Main fields:

- `bird_variant`: Boolean flag to identify bird products.
- `bird_flow`: Commercial broiler or breeder stock.
- `bird_sex`: Male, female, or both.
- `abattoir_type`: Classification used in abattoir output.

### 3.10 `taghini.chicken.batch`

File: `models/batch.py`

Purpose:

- Represents purchased chicken batches.
- Tracks quantity received and how much has been allocated to flocks.

Main fields:

- `name`: Batch reference.
- `date`: Receipt date.
- `supplier_id`: Supplier.
- `total_quantity`: Purchased quantity.
- `series_ids`: Linked flock allocations.
- `allocated_quantity`: Computed allocated quantity.
- `remaining_quantity`: Computed quantity still available.

Main computed logic:

- `_compute_allocation()`: Computes allocated and remaining quantity.

Main actions:

- `create()`: Generates the batch sequence.

### 3.11 `taghini.breeder.batch`

File: `models/breeder.py`

Purpose:

- New breeder-stock workflow record.
- Tracks breeder receiving, male/female split, gift quantities, mortality split, final stocked quantities, and lifecycle stages.

Main fields:

- `name`: Breeder batch reference.
- `date`: Receipt date.
- `company_id`: Company.
- `source_type`: Hatchery or own farm.
- `source_partner_id`: Source partner.
- `source_reference`: Source invoice or reference.
- `bird_variant_id`: Bird variant template.
- `standard_id`: Growth profile.
- `female_order_qty`: Ordered female chicks.
- `male_order_qty`: Computed 12 percent male allocation.
- `gift_total_qty`: Computed gift total.
- `gift_male_qty`: Gift male quantity.
- `gift_female_qty`: Gift female quantity.
- `shipped_male_qty`: Computed shipped male quantity.
- `shipped_female_qty`: Computed shipped female quantity.
- `transit_male_mortality`: In-transit male mortality.
- `transit_female_mortality`: In-transit female mortality.
- `premise_male_mortality`: On-premise male mortality.
- `premise_female_mortality`: On-premise female mortality.
- `stocked_male_qty`: Final stocked male quantity.
- `stocked_female_qty`: Final stocked female quantity.
- `stocked_total_qty`: Final day-one quantity.
- `male_section_qty`: Males placed in male section.
- `female_section_qty`: Females placed in female section.
- `introduced_male_qty`: Males introduced for mating.
- `introduced_female_qty`: Females in mating section.
- `egg_production_qty`: Egg count.
- `current_state_note`: Optional stage note.
- `log_ids`: Breeder daily logs.
- `log_count`: Number of breeder logs.
- `state`: Draft, received, sorted, mating, laying, harvested, closed, cancelled.

Main computed logic:

- `_compute_order_qty()`: Calculates male allocation as 12 percent of female order.
- `_compute_shipped_qty()`: Calculates shipped male and female totals.
- `_compute_gift_qty()`: Calculates total gift quantity.
- `_compute_stocked_qty()`: Calculates final live quantity after mortalities.
- `_compute_log_count()`: Counts breeder logs.

Main actions:

- `create()`: Generates breeder sequence.
- `action_mark_received()`: Marks batch as received.
- `action_mark_sorted()`: Marks batch as sorted.
- `action_mark_mating()`: Marks mating stage.
- `action_mark_laying()`: Marks laying stage.
- `action_mark_harvested()`: Marks harvested stage.
- `action_close_batch()`: Closes breeder batch.
- `action_cancel_batch()`: Cancels breeder batch.

### 3.12 `taghini.breeder.daily.log`

File: `models/breeder.py`

Purpose:

- Daily log for breeder operations.
- Captures store receipts, sorting, mating, laying, health, harvest, and general activities.

Main fields:

- `batch_id`: Parent breeder batch.
- `company_id`: Company.
- `date`: Log date.
- `activity_type`: Receipt, sorting, mating, laying, health, harvest, or general.
- `male_mortality_transit`: Male in-transit mortality.
- `female_mortality_transit`: Female in-transit mortality.
- `male_mortality_premise`: Male on-premise mortality.
- `female_mortality_premise`: Female on-premise mortality.
- `birds_received_male`: Male received.
- `birds_received_female`: Female received.
- `males_sorted`: Males sorted.
- `females_sorted`: Females sorted.
- `males_introduced`: Males introduced for mating.
- `females_placed`: Females placed in section.
- `eggs_collected`: Eggs collected.
- `eggs_sent_to_hatchery`: Eggs sent to hatchery.
- `store_items_received`: Items received from store.
- `observations`: Farm observations.
- `activities`: Farm activities.
- `remarks`: Free-text remarks.
- `state`: Draft or done.

Main actions:

- `action_post_log()`: Marks breeder log as posted.

Main protection:

- `unlink()`: Prevents deletion of posted breeder logs.

## 4. UI Views and Menu Structure

### 4.1 Broiler views

- `views/pen_views.xml`: Pens form/list and pen smart button.
- `views/flock_views.xml`: Main flock workflow form with daily tabs and actions.
- `views/daily_log_views.xml`: Daily log form, list views, analysis actions.
- `views/standard_views.xml`: Growth standard form and configuration menu.
- `views/harvest_views.xml`: Harvest form and list.
- `views/abattoir_views.xml`: Abattoir workflow form and list.
- `views/product_views.xml`: Product template extension for bird flags.
- `views/batch_views.xml`: Purchased batch form and list.
- `views/dashboard.xml`: Dashboard with farm and abattoir graphs.

### 4.2 Breeder views

- `views/breeder_views.xml`: New breeder batch form and list.

### 4.3 Main menus

- `Taghini Farm`
- `Dashboard`
- `Pens / Houses`
- `Purchased Batches`
- `Flocks`
- `Daily Logs`
- `Abattoir Harvest`
- `Abattoir`
- `Configuration`
- `Breeder Stock`

## 5. Current Business Flow

### 5.1 Commercial broiler flow

1. Create or receive a purchased chicken batch.
2. Allocate birds to a flock.
3. Set pen, product, growth profile, and stocking date.
4. Mark the flock as active.
5. Enter daily mortality, feed, water, weight, and vet info.
6. Post daily logs to create stock movements and scrap entries.
7. Confirm harvest when birds are transferred to the abattoir.
8. Confirm abattoir production and post inventory output.
9. Close the flock when finished.

### 5.2 Breeder stock flow

1. Create a breeder batch record.
2. Enter source type, source partner, bird variant, and growth profile.
3. Enter female order quantity.
4. The system calculates the 12 percent male quantity.
5. Enter gift male and gift female quantities.
6. Enter transit mortality by sex.
7. Enter on-premise mortality by sex.
8. Review final stocked male, female, and total day-one quantity.
9. Track sorting and separation of males and females.
10. Track male introduction to females for mating.
11. Track laying stage and egg collection.
12. Optionally track harvest or transfer to abattoir.

## 6. What to Test

### 6.1 Product setup test

Goal:

- Verify bird metadata appears on product templates.

Test steps:

1. Open a product.
2. Mark `Bird Variant` as enabled.
3. Set `Bird Workflow` to broiler or breeder.
4. Set sex applicability.
5. Save and reopen the product.

Expected result:

- Bird fields remain saved and visible.
- Bird-specific products can be selected in flock and breeder forms.

### 6.2 Broiler flock test

Goal:

- Verify current broiler workflow still works.

Test steps:

1. Create a purchased chicken batch.
2. Create a flock from a pen.
3. Select a bird variant product.
4. Select growth profile and batch.
5. Start the flock.
6. Add a daily log.
7. Post the log.
8. Add harvest data.
9. Confirm harvest.

Expected result:

- Stock moves are created.
- Mortality can create scraps.
- Flock current birds update correctly.
- Harvest closes or reduces the flock properly.

### 6.3 Breeder receiving test

Goal:

- Verify breeder quantity calculations.

Test steps:

1. Open Breeder Stock.
2. Create a new breeder batch.
3. Enter female order quantity, for example 1000.
4. Enter gift male and gift female values.
5. Enter transit and premise mortality values.
6. Save the record.

Expected result:

- Male order quantity is auto-calculated as 12 percent of the female order.
- Shipped male and female quantities are calculated.
- Final stocked male, female, and total are computed from mortalities.

### 6.4 Breeder lifecycle test

Goal:

- Verify breeder stage changes and logging.

Test steps:

1. Create a breeder batch.
2. Mark it received.
3. Mark it sorted.
4. Mark it mating.
5. Mark it laying.
6. Add daily breeder log entries for egg collection, sorting, and activities.
7. Mark harvested if needed.

Expected result:

- State transitions work in order.
- Logs are stored under the breeder batch.
- Egg production and activity notes are captured.

### 6.5 Daily log tab test

Goal:

- Verify the reorganized daily log layout.

Test steps:

1. Open a flock.
2. Open the daily log form.
3. Check Vet & Health tab.
4. Check Daily Activities tab.
5. Check Remarks tab.

Expected result:

- Vet data is isolated from remarks.
- Store receipts, observations, and activities are captured separately.

### 6.6 Abattoir test

Goal:

- Verify output production and yield calculation.

Test steps:

1. Create a harvest.
2. Create an abattoir batch from that harvest.
3. Fill output lines.
4. Move through reception, slaughtering, and production.
5. Post inventory.

Expected result:

- Input birds are consumed.
- Output products are posted to stock.
- Yield and processing loss are computed.

## 7. Example Use Cases

### Use case 1: Commercial broiler cycle

Scenario:

The farm receives 5,000 broiler chicks.

What happens:

- A purchased batch is created.
- A flock is created in a pen.
- Daily feed, mortality, and health logs are entered.
- Harvest is confirmed when birds reach market weight.
- Abattoir production is posted.

Outcome:

- The farm knows live birds, mortality, feed use, FCR, harvest performance, and output yield.

### Use case 2: Breeder stock cycle

Scenario:

The farm orders 1,000 breeder females.

What happens:

- The system calculates the male allocation as 12 percent.
- The farm records mixed gift chicks.
- In-transit and on-premise mortality are captured separately by sex.
- Final day-one quantity is calculated.
- Males and females are sorted and tracked separately.
- Males are introduced to females for mating.
- Laying, egg collection, and egg transfer are logged.

Outcome:

- The farm can trace breeder performance from receipt to laying and later harvest if birds are culled or transferred.

### Use case 3: Daily farm activity tracking

Scenario:

The farm receives feed, vaccines, and materials from the store.

What happens:

- The user records store items received.
- The user records farm observations.
- The user records general farm activities.

Outcome:

- Daily operational history is easier to audit and separate from vet remarks.

## 8. Important Notes for the User Guide

- Keep the broiler workflow and breeder workflow separate in the guide.
- Explain that product is still the shared master record because it is used by stock moves and purchase processes.
- Explain that bird-related fields are only meaningful when `Bird Variant` is enabled.
- Explain the difference between transit mortality and on-premise mortality for breeder stock.
- Explain that breeder batch calculations are sex-aware, while commercial broiler flows remain quantity-based.
- Explain that the Daily Activities tab is for general farm work, not vet notes.

## 9. Suggested Next Enhancements

- Add breeder-specific stock move posting logic.
- Add breeder egg production analytics.
- Add sex-based mortality dashboard graphs.
- Add breeder sorting and introduction smart buttons.
- Add reporting for hatchery supply versus own-farm source batches.
