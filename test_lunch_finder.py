import unittest

from lunch_finder import (
    OFFICE_LAT,
    OFFICE_LON,
    cuisine_label,
    distance_meters,
    filter_places,
    hyakumeiten_places,
    remove_closed,
    is_open_at,
    overpass_query,
    parse_element,
    render_html,
)


class LunchFinderTest(unittest.TestCase):
    def test_distance_is_zero_for_same_point(self):
        self.assertEqual(distance_meters(OFFICE_LAT, OFFICE_LON, OFFICE_LAT, OFFICE_LON), 0)

    def test_cuisine_label_translates_and_falls_back(self):
        self.assertEqual(cuisine_label({"cuisine": "ramen;sushi"}), "ラーメン・寿司")
        self.assertEqual(cuisine_label({"cuisine": "ethiopian"}), "ethiopian")
        self.assertEqual(cuisine_label({"amenity": "fast_food"}), "ファストフード")

    def test_parse_element_uses_center_for_ways_and_skips_unnamed(self):
        element = {
            "type": "way",
            "id": 1,
            "center": {"lat": OFFICE_LAT, "lon": OFFICE_LON + 0.001},
            "tags": {"name": "テスト食堂", "amenity": "restaurant", "cuisine": "japanese"},
        }
        place = parse_element(element, OFFICE_LAT, OFFICE_LON)
        self.assertEqual(place["genre"], "和食")
        self.assertGreaterEqual(place["walk_minutes"], 1)
        self.assertGreater(place["meters"], 0)
        self.assertIsNone(parse_element({"type": "node", "id": 2, "lat": 1, "lon": 1, "tags": {}}, 0, 0))

    def test_filter_matches_name_and_genre(self):
        places = [
            {"name": "A", "genre": "ラーメン", "cuisine": "ramen"},
            {"name": "寿司B", "genre": "", "cuisine": ""},
        ]
        self.assertEqual(len(filter_places(places, ["ラーメン"])), 1)
        self.assertEqual(len(filter_places(places, ["RAMEN"])), 1)
        self.assertEqual(len(filter_places(places, ["寿司"])), 1)
        self.assertEqual(len(filter_places(places, [])), 2)

    def test_query_includes_cafe_only_when_requested(self):
        self.assertNotIn("cafe", overpass_query(0, 0, 500, False))
        self.assertIn("cafe", overpass_query(0, 0, 500, True))

    def test_render_html_embeds_places_and_escapes_script_end(self):
        place = {"name": "</script>店", "branch": None, "genre": "", "meters": 10, "walk_minutes": 1,
                 "opening_hours": None, "website": None, "osm": "https://www.openstreetmap.org/node/1",
                 "lat": OFFICE_LAT, "lon": OFFICE_LON}
        html = render_html([place], 500)
        self.assertIn("東劇ビル", html)
        self.assertNotIn("</script>店", html)
        self.assertIn("<\\/script>店", html)

    def test_is_open_at(self):
        monday, saturday = 0, 5
        lunch = "Mo-Fr 11:00-14:30,17:00-22:00"
        self.assertTrue(is_open_at(lunch, monday, 13 * 60 + 30))
        self.assertFalse(is_open_at(lunch, monday, 15 * 60))
        self.assertFalse(is_open_at(lunch, saturday, 13 * 60 + 30))
        self.assertTrue(is_open_at("Mo-Su 11:00-22:00", saturday, 13 * 60 + 30))
        self.assertTrue(is_open_at("11:00-04:30", monday, 2 * 60))
        self.assertTrue(is_open_at("24/7", monday, 0))
        self.assertFalse(is_open_at("Mo-Su 11:00-22:00; Mo off", monday, 13 * 60 + 30))
        self.assertIsNone(is_open_at(None, monday, 0))
        self.assertIsNone(is_open_at("sunrise-sunset", monday, 0))

    def test_remove_closed_matches_name_substring(self):
        places = [{"name": "ほっかい", "branch": None}, {"name": "紅麗", "branch": None}]
        self.assertEqual([p["name"] for p in remove_closed(places, ["ほっかい"])], ["紅麗"])

    def test_hyakumeiten_places_are_flagged_and_limited_by_radius(self):
        near = hyakumeiten_places(OFFICE_LAT, OFFICE_LON, 1000)
        self.assertTrue(near)
        self.assertTrue(all(p["hyakumeiten"] for p in near))
        self.assertEqual(hyakumeiten_places(OFFICE_LAT, OFFICE_LON, 10), [])

    def test_hyakumeiten_lunch_hours(self):
        by_name = {p["name"]: p for p in hyakumeiten_places(OFFICE_LAT, OFFICE_LON, 3000)}
        monday_1330 = (0, 13 * 60 + 30)
        self.assertTrue(is_open_at(by_name["とんかつ はせ川 東銀座店"]["opening_hours"], *monday_1330))
        self.assertFalse(is_open_at(by_name["焼肉うしごろ 銀座並木通り店"]["opening_hours"], *monday_1330))
        self.assertTrue(is_open_at(by_name["焼肉うしごろ 銀座並木通り店"]["opening_hours"], 5, 13 * 60 + 30))
        self.assertFalse(is_open_at(by_name["銀座いち分"]["opening_hours"], *monday_1330))


if __name__ == "__main__":
    unittest.main()
