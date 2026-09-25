import re
import tkinter as tk
from tkinter import ttk

from war3_new_equipment_catalog import EQUIPMENT, CAMPAIGN_SHA256
from war3_new_equipment_ui import NewEquipmentTab, search_equipment
from tools.generate_forsaken_equipment_catalog import text


def test_catalog_is_complete_and_resolved():
    assert re.fullmatch('[0-9a-f]{64}', CAMPAIGN_SHA256)
    assert len(EQUIPMENT) == 184
    assert len({r['code'] for r in EQUIPMENT}) == 184
    for row in EQUIPMENT:
        assert len(row['code']) == 4 and row['code'].isascii()
        assert row['name'] and row['description'] and row['chapters']
        assert not re.search(r'<[^>]+>|TRIGSTR_|未解析|\ufffd|\|c[0-9a-fA-F]{8}', row['description'])


def test_known_helmet_source_values_and_search():
    helmet, = search_equipment('eeh3')
    assert helmet['name'] == '大师级工程护目镜'
    assert '+20%技能速度' in helmet['description']
    assert '+40移动速度' in helmet['description']
    assert '+5点智力' in helmet['description']
    assert {r['code'] for r in search_equipment('工程 技能速度')} == {'eeh1', 'eeh2', 'eeh3'}
    assert search_equipment('EEH3') == (helmet,)
    assert not search_equipment('nonexistent-equipment')


def test_reference_percentage_is_not_a_multiplier_label():
    assert text('|cffffffff+<ACDf,DataA1,%>%|r|n+<AId1,DataA1>点护甲',
                {'ACDf': {'DataA1': '0.2'}, 'AId1': {'DataA1': '1'}}) == '+20%\n+1点护甲'
    assert '未解析' in text('<missing,DataA1>', {})


def test_real_tk_tab_search_selection_and_full_description():
    root = tk.Tk()
    root.withdraw()
    try:
        notebook = ttk.Notebook(root)
        tab = NewEquipmentTab(notebook)
        assert notebook.tab(tab, 'text') == '3.0新装备'
        assert len(tab.tree.get_children()) == 184
        tab.query.set('eeh3')
        assert len(tab.tree.get_children()) == 1
        tab.tree.selection_set('0')
        tab.show_detail()
        assert '大师级工程护目镜' in tab.detail.get()
        assert '+20%技能速度' in tab.detail.get()
        tab.query.set('no-such-code')
        assert not tab.tree.get_children()
        assert tab.selected() is None
        tab.query.set('')
        assert len(tab.tree.get_children()) == 184
    finally:
        root.destroy()
