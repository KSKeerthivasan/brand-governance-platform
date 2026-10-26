import os
from PIL import Image

def test_image_governance_alt_text_and_dimensions(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    
    # Create a small dummy image file
    test_img_path = "./test_creative.png"
    img = Image.new("RGB", (400, 400), color="blue")
    img.save(test_img_path)

    try:
        # Check image with missing alt text
        res = client.post("/api/v1/governance/image-check", headers=headers, json={
            "image_url": test_img_path,
            "channel": "Instagram Post",
            "alt_text": ""  # Missing alt text!
        })
        assert res.status_code == 200
        data = res.json()
        assert not data["passed"]
        
        # Check that accessibility alt-text deficiency is detected
        findings = data["findings"]
        assert any("Accessibility Violation" in f for f in findings)
        assert any("Resolution Deficiency" in f for f in findings)

        # Now test with proper alt text and compliant resolution
        hi_res_path = "./test_hires.png"
        img_hires = Image.new("RGB", (1080, 1080), color="green")
        img_hires.save(hi_res_path)

        res2 = client.post("/api/v1/governance/image-check", headers=headers, json={
            "image_url": hi_res_path,
            "channel": "Instagram Post",
            "alt_text": "Cold refreshing can of Freshsip Sparkling Citrus on sunlit patio table."
        })
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["passed"]
        if os.path.exists(hi_res_path):
            os.remove(hi_res_path)

    finally:
        if os.path.exists(test_img_path):
            os.remove(test_img_path)
