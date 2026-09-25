# Any-slot direct equip guard

The trainer's any-slot setting is currently a per-unit permission for its own
"equip expanded-bag item into selected loadout slot" transaction. It does not
change the game's native drag-and-drop classifier or enable arbitrary item
placement from the game's equipment UI.

Before this change, the direct transaction rejected an already occupied
same-type source slot when the setting was off, but an empty mismatched target
slot passed the guard. It could therefore place the first wrong-type item even
when any-slot was supposedly disabled. The transaction now checks the target
slot type before making any game call. Type 9 (universal) remains accepted.

Verification: 24 focused trainer/equipment tests passed, including a new
wrong-type empty-slot rejection, existing same-type ring conflict, and
universal-type pass-through. Previous live evidence on PID 26456 showed two
head items in head/trinket slots with both armor bonuses active and exact
rollback to baseline; those tests exercise trainer-directed placement only.

Native `UnitEquipItem` chooses its legal slot from the item's runtime type.
The `iequ` field setter returned success in a previous live probe but did not
change `GetItemEquipmentType` or the chosen slot. The packed native handlers
have not yielded a verified runtime classifier override. Game UI drag-and-drop
remains unimplemented and must not be reported as fixed by this guard.
