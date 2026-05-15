from odoo import models, api
import datetime
import logging

_logger = logging.getLogger(__name__)

class VoipCall(models.Model):
    _inherit = 'voip.call'

    @api.model
    def auto_cleanup_duplicates(self):
        """ Auto-cleanup for duplicated VOIP calls from Axivox """
        
        DAYS_BACK = 7 # Look back 7 days [cite: 438]
        TIME_WINDOW_MINUTES = 5 # Group calls within 5 minutes [cite: 438]
        BATCH_SIZE = 500
        
        def normalize_phone(phone):
            """ Strips numbers for comparison (+32... becomes 0032...) """ # [cite: 439]
            if not phone:
                return "UNKNOWN"
            clean = str(phone).replace(" ", "").replace("-", "").replace("/", "").replace(".", "").replace("(", "").replace(")", "")
            if clean.startswith("+"):
                clean = "00" + clean[1:]
            return clean

        time_threshold = datetime.datetime.now() - datetime.timedelta(days=DAYS_BACK)
        calls = self.search([('create_date', '>=', time_threshold)])
        
        # Sort by Phone -> State -> Create Date (Newest first) [cite: 446-447]
        calls_sorted = calls.sorted(key=lambda r: (normalize_phone(r.phone_number), r.state, r.create_date), reverse=True)

        ids_to_delete = []

        if len(calls_sorted) > 1:
            last_kept = calls_sorted[0]
            last_num = normalize_phone(last_kept.phone_number)

            for current in calls_sorted[1:]:
                current_num = normalize_phone(current.phone_number)
                
                if current_num == "UNKNOWN" or len(current_num) < 3: # Skip unknown numbers [cite: 450]
                    last_kept = current
                    last_num = current_num
                    continue

                same_number = (current_num == last_num)
                same_state = (current.state == last_kept.state) # Only delete if status is identical [cite: 451]

                if last_kept.create_date and current.create_date:
                    time_diff = last_kept.create_date - current.create_date
                    within_time = abs(time_diff.total_seconds()) < (TIME_WINDOW_MINUTES * 60)
                else:
                    within_time = False

                if same_number and same_state and within_time: # DUPLICATE [cite: 452-453]
                    ids_to_delete.append(current.id)
                else:
                    # UNIQUE: Becomes the new reference [cite: 453]
                    last_kept = current
                    last_num = current_num

        if ids_to_delete:
            _logger.info(f"VOIP AUTO-CLEANUP: {len(ids_to_delete)} duplicates removed.") # [cite: 455]
            
            for i in range(0, len(ids_to_delete), BATCH_SIZE):
                batch = ids_to_delete[i:i + BATCH_SIZE]
                self.browse(batch).unlink()
                self.env.cr.commit()