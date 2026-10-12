/* Callback-local observations. No extra native calls, probes or game writes. */
#define BRIDGE_JOURNAL_CAPACITY 1024u
typedef struct BridgeNativeEvent {
    uint32_t sequence,native,phase,flags;
    uint64_t a,b,c,d,result;
} BridgeNativeEvent;
typedef struct BridgeNativeJournal {
    uint32_t enabled,count,dropped,phase;
    BridgeNativeEvent last,events[BRIDGE_JOURNAL_CAPACITY];
} BridgeNativeJournal;
_Static_assert(sizeof(BridgeNativeEvent)==56,"Native event ABI");
_Static_assert(sizeof(BridgeNativeJournal)==57416,"Native journal ABI");
static BridgeNativeJournal *bridge_native_journal;
static void BridgeJournalPhase(uint32_t phase) {
    if(bridge_native_journal && bridge_native_journal->enabled)bridge_native_journal->phase=phase;
}
static uint32_t BridgeJournalBegin(uint32_t native,uint64_t a,uint64_t b,uint64_t c,uint64_t d) {
    BridgeNativeJournal *j=bridge_native_journal;
    if(!j || !j->enabled)return UINT32_MAX;
    uint32_t index=j->count;
    BridgeNativeEvent event={j->count+j->dropped+1u,native,j->phase,1u,a,b,c,d,0};
    j->last=event;
    if(index<BRIDGE_JOURNAL_CAPACITY){j->events[index]=event;++j->count;}
    else ++j->dropped;
    return index;
}
static uint64_t BridgeJournalEnd(uint32_t index,uint64_t result) {
    BridgeNativeJournal *j=bridge_native_journal;
    if(j && j->enabled && index!=UINT32_MAX){
        j->last.result=result;j->last.flags|=2u;
        if(index<BRIDGE_JOURNAL_CAPACITY){j->events[index].result=result;j->events[index].flags|=2u;}
    }
    return result;
}

static uint32_t BridgeJournalReal(float*value){union{float real;uint32_t bits;}v;v.real=*value;return v.bits;}
static uint64_t BridgeObservedUnitAbility(uint64_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(1,(uint64_t)a,(uint64_t)b,0,0);
    uint64_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint64_t BridgeObservedUnitAbilityIndex(uint64_t(*fn)(uint64_t,int32_t),uint64_t a,int32_t b) {
    uint32_t index=BridgeJournalBegin(2,(uint64_t)a,(uint64_t)b,0,0);
    uint64_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint32_t BridgeObservedAbilityId(uint32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(3,(uint64_t)a,0,0,0);
    uint32_t value=fn(a);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static int32_t BridgeObservedLevel(int32_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(4,(uint64_t)a,(uint64_t)b,0,0);
    int32_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedAddAbility(uint8_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(5,(uint64_t)a,(uint64_t)b,0,0);
    uint8_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static int32_t BridgeObservedSetLevel(int32_t(*fn)(uint64_t,uint32_t,int32_t),uint64_t a,uint32_t b,int32_t c) {
    uint32_t index=BridgeJournalBegin(6,(uint64_t)a,(uint64_t)b,(uint64_t)c,0);
    int32_t value=fn(a,b,c);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedRemoveAbility(uint8_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(7,(uint64_t)a,(uint64_t)b,0,0);
    uint8_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint64_t BridgeObservedItemAbility(uint64_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(8,(uint64_t)a,(uint64_t)b,0,0);
    uint64_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint64_t BridgeObservedItemAbilityIndex(uint64_t(*fn)(uint64_t,int32_t),uint64_t a,int32_t b) {
    uint32_t index=BridgeJournalBegin(9,(uint64_t)a,(uint64_t)b,0,0);
    uint64_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedAddItemAbility(uint8_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(10,(uint64_t)a,(uint64_t)b,0,0);
    uint8_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint64_t BridgeObservedItemSlot(uint64_t(*fn)(uint64_t,int32_t),uint64_t a,int32_t b) {
    uint32_t index=BridgeJournalBegin(11,(uint64_t)a,(uint64_t)b,0,0);
    uint64_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint32_t BridgeObservedItemType(uint32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(12,(uint64_t)a,0,0,0);
    uint32_t value=fn(a);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static int32_t BridgeObservedCharges(int32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(13,(uint64_t)a,0,0,0);
    int32_t value=fn(a);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint64_t BridgeObservedCreateItem(uint64_t(*fn)(uint32_t,float*,float*),uint32_t a,float* b,float* c) {
    uint32_t index=BridgeJournalBegin(14,(uint64_t)a,BridgeJournalReal(b),BridgeJournalReal(c),0);
    uint64_t value=fn(a,b,c);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedAddItem(uint8_t(*fn)(uint64_t,uint64_t),uint64_t a,uint64_t b) {
    uint32_t index=BridgeJournalBegin(15,(uint64_t)a,(uint64_t)b,0,0);
    uint8_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedMoveItem(uint8_t(*fn)(uint64_t,uint64_t,int32_t),uint64_t a,uint64_t b,int32_t c) {
    uint32_t index=BridgeJournalBegin(16,(uint64_t)a,(uint64_t)b,(uint64_t)c,0);
    uint8_t value=fn(a,b,c);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedAddItemSlot(uint8_t(*fn)(uint64_t,uint32_t,int32_t),uint64_t a,uint32_t b,int32_t c) {
    uint32_t index=BridgeJournalBegin(17,(uint64_t)a,(uint64_t)b,(uint64_t)c,0);
    uint8_t value=fn(a,b,c);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint64_t BridgeObservedRealField(uint64_t(*fn)(uint64_t,uint32_t,int32_t),uint64_t a,uint32_t b,int32_t c) {
    uint32_t index=BridgeJournalBegin(18,(uint64_t)a,(uint64_t)b,(uint64_t)c,0);
    uint64_t value=fn(a,b,c);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedSetRealField(uint8_t(*fn)(uint64_t,uint32_t,int32_t,float*),uint64_t a,uint32_t b,int32_t c,float* d) {
    uint32_t index=BridgeJournalBegin(19,(uint64_t)a,(uint64_t)b,(uint64_t)c,BridgeJournalReal(d));
    uint8_t value=fn(a,b,c,d);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static int32_t BridgeObservedIntegerField(int32_t(*fn)(uint64_t,uint32_t,int32_t),uint64_t a,uint32_t b,int32_t c) {
    uint32_t index=BridgeJournalBegin(20,(uint64_t)a,(uint64_t)b,(uint64_t)c,0);
    int32_t value=fn(a,b,c);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedSetIntegerField(uint8_t(*fn)(uint64_t,uint32_t,int32_t,int32_t),uint64_t a,uint32_t b,int32_t c,int32_t d) {
    uint32_t index=BridgeJournalBegin(21,(uint64_t)a,(uint64_t)b,(uint64_t)c,(uint64_t)d);
    uint8_t value=fn(a,b,c,d);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint32_t BridgeObservedOrder(uint32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(22,(uint64_t)a,0,0,0);
    uint32_t value=fn(a);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedImmediateOrder(uint8_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(23,(uint64_t)a,(uint64_t)b,0,0);
    uint8_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint8_t BridgeObservedPointOrder(uint8_t(*fn)(uint64_t,uint32_t,float*,float*),uint64_t a,uint32_t b,float* c,float* d) {
    uint32_t index=BridgeJournalBegin(24,(uint64_t)a,(uint64_t)b,BridgeJournalReal(c),BridgeJournalReal(d));
    uint8_t value=fn(a,b,c,d);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint32_t BridgeObservedUnitState(uint32_t(*fn)(uint64_t,uint64_t),uint64_t a,uint64_t b) {
    uint32_t index=BridgeJournalBegin(25,(uint64_t)a,(uint64_t)b,0,0);
    uint32_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint32_t BridgeObservedCooldown(uint32_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(26,(uint64_t)a,(uint64_t)b,0,0);
    uint32_t value=fn(a,b);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static void BridgeObservedEndCooldown(void(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(27,(uint64_t)a,(uint64_t)b,0,0);
    fn(a,b);BridgeJournalEnd(index,0);
}
static void BridgeObservedStartCooldown(void(*fn)(uint64_t,uint32_t,float*),uint64_t a,uint32_t b,float* c) {
    uint32_t index=BridgeJournalBegin(28,(uint64_t)a,(uint64_t)b,BridgeJournalReal(c),0);
    fn(a,b,c);BridgeJournalEnd(index,0);
}
static uint64_t BridgeObservedCreateTimer(uint64_t(*fn)(void)) {
    uint32_t index=BridgeJournalBegin(29,0,0,0,0);
    uint64_t value=fn();BridgeJournalEnd(index,(uint64_t)value);return value;
}
static void BridgeObservedStartTimer(void(*fn)(uint64_t,float*,uint32_t,uint64_t),uint64_t a,float* b,uint32_t c,uint64_t d) {
    uint32_t index=BridgeJournalBegin(30,(uint64_t)a,BridgeJournalReal(b),(uint64_t)c,(uint64_t)d);
    fn(a,b,c,d);BridgeJournalEnd(index,0);
}
static uint32_t BridgeObservedTimerElapsed(uint32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(31,(uint64_t)a,0,0,0);
    uint32_t value=fn(a);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static void BridgeObservedDestroyTimer(void(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(32,(uint64_t)a,0,0,0);
    fn(a);BridgeJournalEnd(index,0);
}
static void BridgeObservedDetachItem(void(*fn)(uint64_t,uint64_t),uint64_t a,uint64_t b) {
    uint32_t index=BridgeJournalBegin(33,(uint64_t)a,(uint64_t)b,0,0);
    fn(a,b);BridgeJournalEnd(index,0);
}
static void BridgeObservedRemoveItem(void(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(34,(uint64_t)a,0,0,0);
    fn(a);BridgeJournalEnd(index,0);
}
static uint32_t BridgeObservedUnitX(uint32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(35,(uint64_t)a,0,0,0);
    uint32_t value=fn(a);BridgeJournalEnd(index,(uint64_t)value);return value;
}
static uint32_t BridgeObservedUnitY(uint32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(36,(uint64_t)a,0,0,0);
    uint32_t value=fn(a);BridgeJournalEnd(index,(uint64_t)value);return value;
}

static uint32_t BridgeObservedUnsignedLevel(uint32_t(*fn)(uint64_t,uint32_t),uint64_t a,uint32_t b) {
    uint32_t index=BridgeJournalBegin(4,a,b,0,0);
    uint32_t value=fn(a,b);BridgeJournalEnd(index,value);return value;
}
static uint32_t BridgeObservedUnitType(uint32_t(*fn)(uint64_t),uint64_t a) {
    uint32_t index=BridgeJournalBegin(37,a,0,0,0);
    uint32_t value=fn(a);BridgeJournalEnd(index,value);return value;
}
