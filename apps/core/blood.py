"""
Blood group definitions and red cell compatibility.

This is for whole blood / red cell donation, which is what almost every
request in a local setting is about. Plasma and platelets follow different
rules and are out of scope for now.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class BloodGroup(models.TextChoices):
    A_POS = "A+", "A+"
    A_NEG = "A-", "A-"
    B_POS = "B+", "B+"
    B_NEG = "B-", "B-"
    AB_POS = "AB+", "AB+"
    AB_NEG = "AB-", "AB-"
    O_POS = "O+", "O+"
    O_NEG = "O-", "O-"


# recipient -> donor groups that recipient can safely receive red cells from
_CAN_RECEIVE_FROM: dict[str, frozenset[str]] = {
    "O-": frozenset({"O-"}),
    "O+": frozenset({"O-", "O+"}),
    "A-": frozenset({"O-", "A-"}),
    "A+": frozenset({"O-", "O+", "A-", "A+"}),
    "B-": frozenset({"O-", "B-"}),
    "B+": frozenset({"O-", "O+", "B-", "B+"}),
    "AB-": frozenset({"O-", "A-", "B-", "AB-"}),
    "AB+": frozenset({"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"}),
}


def compatible_donor_groups(recipient_group: str) -> frozenset[str]:
    """Blood groups that can donate red cells to `recipient_group`."""
    try:
        return _CAN_RECEIVE_FROM[recipient_group]
    except KeyError:
        raise ValueError(_("Unknown blood group: %s") % recipient_group) from None


def can_donate_to(donor_group: str, recipient_group: str) -> bool:
    return donor_group in compatible_donor_groups(recipient_group)


def match_priority(donor_group: str, recipient_group: str) -> int:
    """
    Lower is better. Exact group first, then other compatible groups, with
    O- last so the scarce universal donors are not asked first every time.
    """
    if donor_group == recipient_group:
        return 0
    if donor_group == "O-":
        return 2
    return 1
