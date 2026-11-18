import sys
import os
from unittest.mock import MagicMock
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from due_diligence_agent import (
    MarketValuationAssessment,
    search_tavily_real_estate,
    valuation_investigation_node,
    synthesize_dossier_node,
    DueDiligenceState,
)


def test_market_valuation_assessment_schema_supports_live_market_listings():
    """Kiểm tra schema MarketValuationAssessment hỗ trợ trường live_market_listings"""
    data = {
        "unit_price_per_m2": 55000000.0,
        "avg_district_price_per_m2": 50000000.0,
        "valuation_status": "fair",
        "comparable_properties": [],
        "live_market_listings": [
            {
                "title": "Bán nhà 3 tầng Hải Châu 75m2",
                "url": "https://batdongsan.com.vn/ban-nha-hai-chau-123",
                "snippet": "Nhà đẹp trung tâm quận Hải Châu, giá 5.5 tỷ",
                "source_domain": "batdongsan.com.vn"
            }
        ]
    }
    assessment = MarketValuationAssessment(**data)
    assert len(assessment.live_market_listings) == 1
    assert assessment.live_market_listings[0]["source_domain"] == "batdongsan.com.vn"
    assert assessment.live_market_listings[0]["url"] == "https://batdongsan.com.vn/ban-nha-hai-chau-123"


def test_search_tavily_real_estate_success_with_mock_client():
    """Kiểm tra hàm search_tavily_real_estate trích xuất đúng danh sách tin đăng từ mock TavilyClient"""
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "title": "Bán nhà mặt tiền đường Phan Châu Trinh, Hải Châu",
                "url": "https://chotot.com/mua-ban-nha-dat-hai-chau/101.htm",
                "content": "Nhà đẹp 4 tầng diện tích 80m2, giá 7 tỷ, sổ đỏ chính chủ."
            },
            {
                "title": "Căn hộ cao cấp The Royal view sông Hàn",
                "url": "https://batdongsan.com.vn/ban-can-ho-the-royal/202.htm",
                "content": "Căn hộ 2PN 70m2 full nội thất, giá 4.5 tỷ."
            }
        ]
    }

    listings = search_tavily_real_estate(
        query="nhà phố Hải Châu",
        district="Hải Châu",
        max_results=2,
        tavily_client=mock_client
    )

    assert len(listings) == 2
    assert listings[0]["title"] == "Bán nhà mặt tiền đường Phan Châu Trinh, Hải Châu"
    assert listings[0]["source_domain"] == "chotot.com"
    assert "chotot.com" in listings[0]["url"]
    assert listings[1]["source_domain"] == "batdongsan.com.vn"
    mock_client.search.assert_called_once()


def test_search_tavily_real_estate_graceful_fallback_on_error():
    """Kiểm tra search_tavily_real_estate bắt ngoại lệ và trả về list rỗng mà không crash"""
    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("Tavily API quota exceeded or connection timed out")

    listings = search_tavily_real_estate(
        query="nhà phố Hải Châu",
        district="Hải Châu",
        max_results=3,
        tavily_client=mock_client
    )

    assert isinstance(listings, list)
    assert len(listings) == 0


def test_search_tavily_real_estate_with_none_client_returns_empty_or_offline_fallback():
    """Kiểm tra khi client là None (chưa cấu hình API key) hàm xử lý an toàn"""
    listings = search_tavily_real_estate(
        query="nhà phố Sơn Trà",
        district="Sơn Trà",
        max_results=3,
        tavily_client=None
    )
    assert isinstance(listings, list)


def test_valuation_investigation_node_populates_live_market_listings(monkeypatch):
    """Kiểm tra valuation_investigation_node gắn live_market_listings vào state valuation"""
    mock_listings = [
        {
            "title": "Bán nhà mặt tiền Sơn Trà 100m2",
            "url": "https://batdongsan.com.vn/son-tra-1",
            "snippet": "Vị trí sát biển, giá 6 tỷ",
            "source_domain": "batdongsan.com.vn"
        }
    ]

    import due_diligence_agent as dda
    monkeypatch.setattr(dda, "search_tavily_real_estate", lambda *args, **kwargs: mock_listings)

    state = {
        "property_title": "Nhà phố Sơn Trà",
        "property_price": 6000000000.0,
        "area_m2": 100.0,
        "district": "Sơn Trà",
        "ward": "An Hải Bắc",
        "investment_objective": "residential"
    }

    result = valuation_investigation_node(state)
    assert "valuation" in result
    val_data = result["valuation"]
    assert "live_market_listings" in val_data
    assert len(val_data["live_market_listings"]) == 1
    assert val_data["live_market_listings"][0]["source_domain"] == "batdongsan.com.vn"


def test_synthesize_dossier_node_includes_web_listings_in_markdown(monkeypatch):
    """Kiểm tra synthesize_dossier_node đưa danh sách tin đăng vào báo cáo Markdown"""
    mock_listings = [
        {
            "title": "Nhà kiệt ô tô Hải Châu 70m2",
            "url": "https://chotot.com/hai-chau-kiet-oto",
            "snippet": "Gần cầu Rồng, giá 4.8 tỷ",
            "source_domain": "chotot.com"
        }
    ]

    state = {
        "property_title": "Nhà phố Hải Châu",
        "property_price": 5000000000.0,
        "area_m2": 80.0,
        "district": "Hải Châu",
        "ward": "Hải Châu 1",
        "investment_objective": "residential",
        "legal": {
            "zoning_status": "Quy hoạch ODT",
            "title_deed_status": "Sổ hồng",
            "risks_detected": [],
            "legal_safety_score": 90,
            "citations": []
        },
        "valuation": {
            "unit_price_per_m2": 62500000.0,
            "avg_district_price_per_m2": 75000000.0,
            "valuation_status": "under_priced",
            "comparable_properties": [],
            "live_market_listings": mock_listings
        },
        "climate_infrastructure": {
            "flood_risk_level": "low",
            "flood_notes": "Khu vực an toàn",
            "infrastructure_score": 90,
            "key_amenities": []
        },
        "financial": {
            "monthly_repayment_vnd": 25000000.0,
            "effective_interest_rate": 8.5,
            "estimated_monthly_rental_income": 15000000.0,
            "net_rental_yield_percent": 3.5,
            "dscr_ratio": 0.6,
            "stress_test_passed": True
        },
        "critic_counterarguments": ["Rủi ro lãi suất"],
        "actionable_negotiation_points": ["Đàm phán cọc 5%"]
    }

    result = synthesize_dossier_node(state)
    assert "dossier" in result
    dossier = result["dossier"]
    md = dossier["full_markdown_report"]
    assert "Tin đăng Tham khảo Thực tế từ Thị trường" in md
    assert "chotot.com" in md
    assert "https://chotot.com/hai-chau-kiet-oto" in md
