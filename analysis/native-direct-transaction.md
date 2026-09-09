# Direct ability transaction (protocol 50)

The four single-unit direct-effect entry points (target, immediate, point,
derived no-argument) now send op 136 plus op 157 in one command. Python sends
the unit identity, ability rawcode and effect parameters; it no longer reads
the ability vtable, discovers internal ability functions, or waits between
creation, execution and removal on these paths. Target callbacks receive the
engine unit object; JASS lookup/add/remove receive the JASS handle.

The DLL looks up an existing ability through the bound native table and object
resolvers. If absent, UnitAddAbility asks the engine to create it from the map
resource. A captured wrapper/data generation and backlinks are checked before
the direct callback. This does not require another unit owning the ability.
The actual resource compatibility of this creation route for direct effects
still needs game testing on 2.0.4.23745; fake natives cannot establish it.

Temporary removal runs after both success and exceptions, but only after the
original unit and captured ability identity and level are proven unchanged.
If a trigger removed the ability already, there is nothing to delete. If it
replaced/recycled/modified the ability, cleanup refuses to delete that object.
An exception or inconsistent return during creation can leave ownership
unproven; the command reports the cleanup error rather than guessing what to
remove. An executed gameplay effect cannot be rolled back by this transaction.

The former unreachable Python implementation has been removed. Invalid effect
parameters are rejected before creation. Invalid/incomplete response payloads
cannot be interpreted as success. Protocol 50 is shared by Python and C.

Validation evidence:

- 86 tests in `test_native_direct_transaction.py` and
  `test_native_ability_actions.py` passed (6.54 s). The direct fixture executes
  the production C dispatcher using isolated fake engine functions. It covers
  all four callback argument layouts, existing and absent abilities, callback
  exceptions, unit/ability generations, wrapper ownership, changed levels,
  self-removal, invalid vtables, missing natives and creation/removal failures.
- The optimized helper was rebuilt and copied to `tools/war3_native_helper.dll`.
  SHA256: `a3916bd1a3375c8cf83128e3340b227f0d5381fa8aca3e6855e3a8cffe1656b6`.
- Final full regression: **794 tests and 103 subtests passed** (38.56 s),
  recorded in `analysis/direct-native-v50-regression.log`. The initial run
  exposed an old test's literal protocol 49 assertion; it now checks the
  current protocol constant, alongside the existing Python/C parity test.

No current user gameplay acceptance is claimed. No game mutations or EXE
packaging were performed for this change. Application version remains 1.0.19.

Remaining work includes the roar/buff, sustained-area and world-enumeration
direct-effect paths, which still use controller-side ability discovery; the
compatibility class's selection context also still needs auditing. This
increment does not establish whole-goal completion or measured game speed.
