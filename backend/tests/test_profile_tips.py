import unittest

from resume_parser.profile_tips import generate_profile_tips

RESUME = "Python developer. Built REST APIs with Flask and PostgreSQL. Used Docker and Git."
POSTINGS = [
    "Backend engineer: Python, Django, REST APIs, PostgreSQL, Docker, Kubernetes, CI/CD, AWS.",
    "Looking for a Python engineer with AWS, Kubernetes, microservices, REST APIs and PostgreSQL.",
    "Backend developer. Python, FastAPI, Docker, AWS, CI/CD pipelines, microservices, REST APIs.",
]


class ProfileTipsTests(unittest.TestCase):
    def setUp(self):
        self.tips = generate_profile_tips(RESUME, POSTINGS, "backend engineer", current_headline="Python developer")
        self.missing = [k.keyword for k in self.tips.missing_keywords]
        self.matched = [k.keyword for k in self.tips.matched_keywords]

    def test_missing_keywords_found(self):
        self.assertIn("aws", self.missing)
        self.assertIn("kubernetes", self.missing)

    def test_matched_keywords_found(self):
        self.assertIn("python", self.matched)
        self.assertIn("docker", self.matched)

    def test_role_words_are_not_keywords(self):
        self.assertNotIn("engineer", self.missing)
        self.assertNotIn("backend", self.missing)

    def test_headline_only_uses_resume_keywords(self):
        for headline in self.tips.headline_suggestions:
            self.assertNotIn("aws", headline.lower())

    def test_summary_suggestion_present(self):
        self.assertTrue(self.tips.summary_suggestions)

    def test_no_postings_gives_note(self):
        tips = generate_profile_tips(RESUME, [], "backend engineer")
        self.assertEqual(tips.missing_keywords, [])
        self.assertTrue(tips.notes)


if __name__ == "__main__":
    unittest.main()
