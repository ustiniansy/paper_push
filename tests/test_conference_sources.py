import unittest
from datetime import datetime
from unittest.mock import patch

import requests

from sources.conference_sources import (
    _extract_aaai_archive_papers,
    _extract_acl_event_papers,
    _extract_cvf_papers,
    _fetch_from_url,
    VenueConfig,
    _year_candidates,
    _extract_pmlr_papers,
)


class ConferenceSourceParserTests(unittest.TestCase):
    def test_extract_cvf_papers(self):
        html = """
        <dt class="ptitle"><br><a href="/content/CVPR2025/html/Foo_paper.html">
        Temporal Video Grounding with Agents
        </a></dt>
        <dt class="ptitle"><br><a href="/content/CVPR2025/html/Bar_paper.html">
        Workshop Schedule
        </a></dt>
        """
        papers = _extract_cvf_papers("https://openaccess.thecvf.com/CVPR2025?day=all", html)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Temporal Video Grounding with Agents")

    def test_extract_acl_event_papers(self):
        html = """
        <a class=align-middle href=/volumes/2025.acl-long/>Proceedings of ACL</a>
        <strong><a class=align-middle href=/2025.acl-long.1/>
        GraphNarrator: Generating Textual Explanations for Graph Neural Networks
        </a></strong>
        <strong><a class=align-middle href=/2025.acl-long.0/>
        Proceedings of ACL Volume 1
        </a></strong>
        """
        papers = _extract_acl_event_papers("https://aclanthology.org/events/acl-2025/", html)
        self.assertEqual(len(papers), 1)
        self.assertIn("GraphNarrator", papers[0]["title"])

    def test_extract_pmlr_papers(self):
        html = """
        <div class="paper">
          <p class="title">Aggregation of Dependent Expert Distributions in Multimodal Variational Autoencoders</p>
          <p class="links">
            [<a href="https://proceedings.mlr.press/v267/a-mancisidor25a.html">abs</a>]
          </p>
        </div>
        """
        papers = _extract_pmlr_papers("https://proceedings.mlr.press/v267/", html)
        self.assertEqual(len(papers), 1)
        self.assertEqual(
            papers[0]["url"],
            "https://proceedings.mlr.press/v267/a-mancisidor25a.html",
        )

    def test_extract_aaai_archive_papers(self):
        archive_html = """
        <a href="/index.php/AAAI/issue/view/900">AAAI 2025</a>
        """
        issue_html = """
        <a href="/index.php/AAAI/article/view/12345">Long Video Reasoning with Structured Tools</a>
        <a href="/index.php/AAAI/article/view/12346">Poster</a>
        """
        with patch("sources.conference_sources._get", return_value=issue_html):
            papers = _extract_aaai_archive_papers("https://ojs.aaai.org/index.php/AAAI/issue/archive", archive_html)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Long Video Reasoning with Structured Tools")

    def test_year_candidates_use_current_and_next_year(self):
        with patch("sources.conference_sources.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 19)
            self.assertEqual(_year_candidates(), (2026, 2027))

    def test_fetch_from_url_maps_404_to_not_released(self):
        venue = VenueConfig(
            key="CVPR",
            display_name="CVPR",
            parser="cvf",
            urls=["https://openaccess.thecvf.com/CVPR2026?day=all"],
        )
        response = requests.Response()
        response.status_code = 404
        error = requests.HTTPError("404 Client Error", response=response)
        with patch("sources.conference_sources._get", side_effect=error):
            result = _fetch_from_url(venue, 8)
        self.assertEqual(result.status, "not_released")
        self.assertEqual(result.papers, [])


if __name__ == "__main__":
    unittest.main()
