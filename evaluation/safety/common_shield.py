"""Frozen common pilot shield; predicate priority is unchanged."""

def shield_violation(self,o,peak,drift):
    return ('COLLISION' if o.hand.collision.value else 'WRENCH_LIMIT_EXCEEDED' if peak>self.force_limit else
               'ACTUATOR_LIMIT' if self.saturated_s>.2 else 'PREMATURE_CONTACT' if self.task=='A' and o.contacts else
               'PREMATURE_CONTACT' if any(c.contact_group_id not in {g.group_id for g in self.groups} for c in o.contacts) else
               'OBJECT_DISPLACED' if self.task=='B' and drift>.015 else None)
