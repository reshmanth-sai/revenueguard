import json
import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("revenueguard")

# Synthetic datasets for demonstration
COMPETITORS = {
    "COMP-A": {
        "name": "CloudCorp",
        "pricing": "Enterprise Plan: $85/user/month (recently reduced from $100)",
        "promotions": "Get 3 months free for new switchers",
        "features": "Added advanced AI dashboard and automated reporting"
    },
    "COMP-B": {
        "name": "SaaSify",
        "pricing": "Enterprise Plan: $95/user/month",
        "promotions": "None active",
        "features": "Standard CRM features"
    }
}

CUSTOMERS = {
    "ACC-101": {
        "name": "TechCorp",
        "email": "contact@techcorp.com",
        "monthly_spend": 5000.0,
        "usage_trend": "Declining (-25% last 30 days)",
        "active_users": 15,
        "support_tickets_count": 8,
        "payment_status": "Paid",
    },
    "ACC-102": {
        "name": "BizGrow",
        "email": "billing@bizgrow.com",
        "monthly_spend": 12000.0,
        "usage_trend": "Growing (+15% last 30 days)",
        "active_users": 120,
        "support_tickets_count": 1,
        "payment_status": "Paid",
    },
    "ACC-103": {
        "name": "EcoStore",
        "email": "help@ecostore.org",
        "monthly_spend": 2000.0,
        "usage_trend": "Flat",
        "active_users": 8,
        "support_tickets_count": 12,
        "payment_status": "Overdue (15 days)",
    }
}

@mcp.tool()
def get_competitor_pricing(competitor_id: str) -> str:
    """Gets the current pricing, promotions, and features for a specified competitor.

    Args:
        competitor_id: The ID of the competitor (e.g., COMP-A, COMP-B).
    """
    comp = COMPETITORS.get(competitor_id.upper())
    if not comp:
        return f"Competitor {competitor_id} not found. Available competitors: {', '.join(COMPETITORS.keys())}"
    return json.dumps(comp, indent=2)

@mcp.tool()
def get_customer_usage(customer_id: str) -> str:
    """Gets usage trend, spend, and support metrics for a specific customer account.

    Args:
        customer_id: The ID of the customer (e.g., ACC-101, ACC-102).
    """
    cust = CUSTOMERS.get(customer_id.upper())
    if not cust:
        return f"Customer {customer_id} not found. Available customers: {', '.join(CUSTOMERS.keys())}"
    return json.dumps(cust, indent=2)

@mcp.tool()
def calculate_churn_score(customer_data_json: str) -> str:
    """Calculates a simulated churn risk score (0.0 to 1.0) based on customer metrics.

    Args:
        customer_data_json: A JSON string containing customer details.
    """
    try:
        data = json.loads(customer_data_json)
        score = 0.1  # base risk
        
        # Factor: usage trend
        trend = data.get("usage_trend", "").lower()
        if "declining" in trend:
            score += 0.4
        elif "flat" in trend:
            score += 0.1
            
        # Factor: support tickets
        tickets = int(data.get("support_tickets_count", 0))
        if tickets > 10:
            score += 0.3
        elif tickets > 5:
            score += 0.15
            
        # Factor: payment status
        payment = data.get("payment_status", "").lower()
        if "overdue" in payment:
            score += 0.2
            
        score = min(score, 1.0)
        return json.dumps({"churn_risk_score": score, "confidence": 0.85})
    except Exception as e:
        return json.dumps({"error": f"Invalid customer data format: {str(e)}"})

@mcp.tool()
def estimate_revenue_at_risk(customer_id: str, competitor_id: str) -> str:
    """Estimates the total revenue at risk based on the customer spend and competitor threats.

    Args:
        customer_id: Customer Account ID (e.g., ACC-101).
        competitor_id: Competitor ID (e.g., COMP-A).
    """
    cust = CUSTOMERS.get(customer_id.upper())
    comp = COMPETITORS.get(competitor_id.upper())
    
    if not cust:
        return f"Customer {customer_id} not found."
    if not comp:
        return f"Competitor {competitor_id} not found."
        
    spend = cust.get("monthly_spend", 0.0)
    # Risk factor formula based on churn indicators
    usage_trend = cust.get("usage_trend", "").lower()
    risk_factor = 0.5  # default risk factor
    if "declining" in usage_trend:
        risk_factor += 0.3
        
    revenue_at_risk = spend * risk_factor * 12  # Annualized spend at risk
    
    return json.dumps({
        "customer_id": customer_id,
        "monthly_spend": spend,
        "annualized_value": spend * 12,
        "risk_factor": risk_factor,
        "revenue_at_risk_annualized": revenue_at_risk,
        "explanation": f"Annualized spend at risk is estimated at ${revenue_at_risk:,.2f} because the customer shows {usage_trend} usage and competitor {competitor_id} launched aggressive promotions."
    })

@mcp.tool()
def log_retention_action(customer_id: str, action: str, approved_by: str) -> str:
    """Logs the recommended retention action in the CRM.

    Args:
        customer_id: Customer Account ID (e.g., ACC-101).
        action: The recommended retention strategy/discount.
        approved_by: The entity approving the action (e.g. human_user, system).
    """
    log_entry = {
        "status": "success",
        "customer_id": customer_id,
        "action": action,
        "approved_by": approved_by,
        "logged_at": datetime.datetime.now(datetime.UTC).isoformat()
    }
    print(f"CRM LOG: {json.dumps(log_entry)}")
    return json.dumps(log_entry)

if __name__ == "__main__":
    mcp.run()
