"""Slack alerts via an Incoming Webhook (a URL you POST JSON to)."""
import httpx


def send_slack(webhook: str, text: str) -> bool:
    if not webhook:
        print("[slack] SLACK_WEBHOOK_URL not set - message would have been:\n" + text)
        return False
    try:
        httpx.post(webhook, json={"text": text}, timeout=10).raise_for_status()
        print("[slack] alert sent")
        return True
    except Exception as e:  # noqa: BLE001 - alert failure must never crash the pipeline
        print(f"[slack] failed to send: {e}")
        return False
