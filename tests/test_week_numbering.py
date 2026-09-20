import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import deployable_lms  # noqa: E402


class WeekNumberingTests(unittest.TestCase):
    def test_course_week_maps_to_one_based_frappe_chapter(self):
        self.assertEqual(deployable_lms.week_to_chapter(0), 1)
        self.assertEqual(deployable_lms.week_to_chapter(1), 2)
        self.assertEqual(deployable_lms.week_to_chapter(14), 15)

    def test_frappe_chapter_maps_to_zero_based_course_week(self):
        self.assertEqual(deployable_lms.chapter_to_week(1), 0)
        self.assertEqual(deployable_lms.chapter_to_week(2), 1)
        self.assertEqual(deployable_lms.chapter_to_week(15), 14)

    def test_next_position_returns_semantic_course_week(self):
        outline = [
            {"lessons": [{"number": "1-1", "is_complete": True}]},
            {"lessons": [{"number": "1-3", "is_complete": False}]},
        ]
        with patch.object(deployable_lms, "course_outline", return_value=outline):
            self.assertEqual(
                deployable_lms.next_position("https://lms.opsandplatforms.com", Path("cookies")),
                (0, 3),
            )

    def test_invalid_frappe_chapter_is_rejected(self):
        with self.assertRaises(ValueError):
            deployable_lms.chapter_to_week(0)

    def test_completing_week_zero_marks_frappe_chapter_one(self):
        with (
            patch.object(sys, "argv", ["deployable_lms.py", "0", "--lesson", "3", "--complete"]),
            patch.object(deployable_lms, "load_session", return_value=True),
            patch.object(deployable_lms, "save_session"),
            patch.object(deployable_lms, "request", return_value={"message": "ok"}) as request,
            redirect_stdout(StringIO()),
        ):
            self.assertEqual(deployable_lms.main(), 0)

        progress = request.call_args.args[3]
        self.assertEqual(progress["chapter_number"], 1)
        self.assertEqual(progress["lesson_number"], 3)


if __name__ == "__main__":
    unittest.main()
