import unittest

from scripts.update_ads import interesting_score


class RelevanceRulesTest(unittest.TestCase):
    def test_named_influence_always_included(self):
        text = "Kapela hledá baskytaristku. Inspirace: The Plot In You, Dayseeker, Normandie."
        score, reasons = interesting_score(text, "Praha")
        self.assertEqual(score, 99)
        self.assertIn("The Plot In You", reasons)

    def test_gender_or_age_does_not_block_networking_radar(self):
        text = "Ženská kapela, věkově kolem 40 let. Inspirace Bad Omens a Motionless In White."
        score, reasons = interesting_score(text, "Kralupy nad Vltavou")
        self.assertEqual(score, 99)
        self.assertIn("Bad Omens", reasons)

    def test_priority_genre_is_guaranteed(self):
        score, reasons = interesting_score("Hledáme zpěv na nu-metal.", "Brno")
        self.assertGreaterEqual(score, 88)
        self.assertTrue(any("nu" in reason for reason in reasons))

    def test_prague_is_independently_relevant(self):
        score, reasons = interesting_score("Zakládáme nový hudební projekt.", "Praha 9")
        self.assertGreaterEqual(score, 66)
        self.assertIn("lokální networking", reasons)

    def test_social_or_music_link_is_a_large_bonus(self):
        without_link, _ = interesting_score("Hledám alt-rock kapelu.", "Brno")
        with_link, reasons = interesting_score("Hledám alt-rock kapelu. Instagram: example_band", "Brno")
        self.assertGreater(with_link, without_link)
        self.assertIn("odkaz na profil / ukázku", reasons)

    def test_detailed_serious_ad_needs_no_genre_or_reference_band(self):
        text = ("Zakládáme autorský projekt s vlastní tvorbou. Máme zkušenosti s koncerty a nahráváním, "
                "vybavenou zkušebnu a jasný dlouhodobý plán. Hledáme spolehlivého člověka, který chce pravidelně "
                "zkoušet, podílet se na skládání a postupně vydávat singly a hrát živě. " * 2)
        score, reasons = interesting_score(text, "Plzeň")
        self.assertGreaterEqual(score, 60)
        self.assertIn("podrobný inzerát", reasons)


if __name__ == "__main__":
    unittest.main()
