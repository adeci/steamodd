import unittest
import re
from steam import items
from steam import sim

class BaseTestCase(unittest.TestCase):
    TEST_APP = (440, 'en_US')     # TF2 English catalog
    ITEM_IN_CATALOG = 344         # Crocleather Slouch
    ITEM_NOT_IN_CATALOG = 1       # Bottle
    TEST_ID64 = 76561198811195748 # lagg-bot test acct

    TEST_APP_NO_TAGS = (570, 'en_US')     # Dota 2 English catalog
    ITEM_IN_NO_TAGS_CATALOG = 4097         # Arctic Hunter's Ice Axe

class AssetTestCase(BaseTestCase):
    def test_asset_contains(self):
        assets = items.assets(*self.TEST_APP)
        self.assertTrue(self.ITEM_IN_CATALOG in assets)
        self.assertFalse(self.ITEM_NOT_IN_CATALOG in assets)
        schema = items.schema(*self.TEST_APP)
        self.assertTrue(schema[self.ITEM_IN_CATALOG] in assets)
        self.assertFalse(schema[self.ITEM_NOT_IN_CATALOG] in assets)

    def test_asset_has_tags(self):
        assets_with_tags = items.assets(*self.TEST_APP)
        self.assertGreater(len(assets_with_tags.tags), 0)

    def test_asset_has_no_tags(self):
        assets_without_tags = items.assets(*self.TEST_APP_NO_TAGS)
        self.assertEqual(len(assets_without_tags.tags), 0)

    def test_asset_item_has_tags(self):
        assets_with_tags = items.assets(*self.TEST_APP)
        asset_item_with_tags = assets_with_tags[self.ITEM_IN_CATALOG]
        self.assertGreater(len(asset_item_with_tags.tags), 0)

    def test_asset_item_has_no_tags(self):
        assets_without_tags = items.assets(*self.TEST_APP_NO_TAGS)
        asset_item_without_tags = assets_without_tags[self.ITEM_IN_NO_TAGS_CATALOG]
        self.assertEqual(len(asset_item_without_tags.tags), 0)


class InventoryBaseTestCase(BaseTestCase):
    _inv_cache = None
    _schema_cache = None
    _sim_cache = None

    @property
    def _inv(self):
        if not InventoryBaseTestCase._inv_cache:
            InventoryBaseTestCase._inv_cache = items.inventory(self.TEST_ID64, self.TEST_APP[0], self._schema)

        return InventoryBaseTestCase._inv_cache

    @property
    def _schema(self):
        if not InventoryBaseTestCase._schema_cache:
            InventoryBaseTestCase._schema_cache = items.schema(*self.TEST_APP)

        return InventoryBaseTestCase._schema_cache

    @property
    def _sim(self):
        if not InventoryBaseTestCase._sim_cache:
            InventoryBaseTestCase._sim_cache = sim.inventory(self.TEST_ID64, 440, 2, None, 2000)

        return InventoryBaseTestCase._sim_cache

class ItemTestCase(InventoryBaseTestCase):
    def test_position(self):
        for item in self._inv:
            self.assertLessEqual(item.position, self._inv.cells_total)

    def test_equipped(self):
        for item in self._inv:
            self.assertNotIn(0, item.equipped.keys())
            self.assertNotIn(65535, item.equipped.values())

    def test_name(self):
        # Since sim names are generated by Valve we'll test against those for consistency
        # steamodd adds craft numbers to all names, valve doesn't, so they should be stripped
        # steamodd doesn't add crate series to names, valve does, so they should be stripped as well
        cn_exp = re.compile(r" (?:Series )?#\d+$")

        sim_names = set()
        for item in self._sim:
            # Removes quotes in case of custom name (steamodd leaves that aesthetic choice to the user)
            name = item.full_name.strip("'")

            # Don't even bother with strange items right now. I'm tired of unit tests failing whenever
            # the inventory does and no one from valve responds when I tell them of the issue. If it does
            # get fixed feel free to remove this as it is definitely a WORKAROUND.
            # Removes quotes in case of custom name (steamodd leaves that aesthetic choice to the user)
            if not name.startswith("Strange "):
                sim_names.add(cn_exp.sub('', name))

        # See the above WORKAROUND about strange items and remove if/when it's fixed.
        our_names = set([cn_exp.sub('', item.custom_name or item.full_name) for item in self._inv if item.quality[1] != "strange" or item.custom_name])

        self.assertEqual(our_names, sim_names)

    def test_attributes(self):
        # Similarly to the name, we'll test against Valve's strings to check for consistency in the math.
        schema_attr_exps = []
        for attr in self._schema.attributes:
            if not attr.description:
                continue

            desc = attr.description.strip()
            exp = re.escape(desc).replace("\\%s1", r"[\d-]+")

            schema_attr_exps.append(re.compile(exp))

        sim_attrs = {}
        for item in self._sim:
            sim_attrs.setdefault(item.id, set())

            for attr in item:
                # Due to lack of contextual data, we'll have to do fuzzy matching to separate actual attrs from fluff/descriptions
                desc = attr.description.strip()
                if desc:
                    # Stop processing if we hit item set attrs, for now
                    if desc.startswith("Item Set Bonus:"):
                        break

                    # Valve for some reason insists on this being attached by the client, since they're not actually attached we skip it.
                    if desc == "Given to valuable Community Contributors":
                        continue

                    for exp in schema_attr_exps:
                        if exp.match(desc):
                            sim_attrs[item.id].add(desc)
                            break

        for item in self._inv:
            # Ignore hidden, special (for now) and date values (timestamp formatting is an eternal battle, let it not be fought on these hallowed testgrounds)
            attrs = set([attr.formatted_description for attr in item if not attr.hidden and
                                                                        not attr.formatted_description.startswith("Attrib_") and
                                                                        attr.value_type not in ("date", "particle_index")])
            self.assertTrue(item.id in sim_attrs)
            self.assertEqual(attrs, sim_attrs[item.id])

class InventoryTestCase(InventoryBaseTestCase):
    def test_cell_count(self):
        self.assertLessEqual(len(list(self._inv)), self._inv.cells_total)
