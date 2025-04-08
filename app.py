from flask import Flask, render_template, request, jsonify
import requests
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io
import base64
import time

app = Flask(__name__)

# Cache for scheme data
scheme_cache = None
scheme_last_fetched = 0


def get_all_schemes():
    global scheme_cache, scheme_last_fetched
    # Cache for 1 hour
    if scheme_cache is None or time.time() - scheme_last_fetched > 3600:
        url = "https://investyadnya.in/searchForPortfolioOverlapSchemes?searchString="
        response = requests.get(url)
        data = response.json()
        scheme_cache = {
            scheme["SchemeId"]: scheme["SchemeName"] for scheme in data.get("data", [])
        }
        scheme_last_fetched = time.time()
    return scheme_cache


def get_portfolio_overlap(scheme_id_A, scheme_id_B):
    url = f"https://investyadnya.in/getCommonUncommonStocksData?schemeId_A={scheme_id_A}&schemeId_B={scheme_id_B}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("status") == "success":
            return data["data"].get("PortfolioOverlapPercent", np.nan)
        return np.nan
    except:
        return np.nan


def create_heatmap(scheme_ids, scheme_names):
    n = len(scheme_ids)
    overlap_matrix = np.zeros((n, n))

    # Get all unique pairs
    for i in range(n):
        for j in range(i + 1, n):
            overlap = get_portfolio_overlap(scheme_ids[i], scheme_ids[j])
            overlap_matrix[i, j] = overlap
            overlap_matrix[j, i] = overlap
            time.sleep(0.5)  # Rate limiting

    np.fill_diagonal(overlap_matrix, 100)

    # Create plot
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        overlap_matrix,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        xticklabels=scheme_names,
        yticklabels=scheme_names,
        vmin=0,
        vmax=100,
        square=True,
    )
    plt.title("Portfolio Overlap Heatmap")
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()

    # Convert plot to base64 for HTML
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close()

    return img_base64


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search_schemes")
def search_schemes():
    query = request.args.get("q", "").lower()
    schemes = get_all_schemes()
    results = [{"id": k, "name": v} for k, v in schemes.items() if query in v.lower()][
        :20
    ]  # Limit to 20 results
    return jsonify(results)


# Add this new function to fetch expense ratio
def get_expense_ratio(scheme_id):
    url = f"https://investyadnya.in/getFundCompanySchemeDetails?fundId={scheme_id}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("status") == "success":
            return data["data"].get("expenseRatio", "N/A")
        return "N/A"
    except:
        return "N/A"


# Modify the compare route to include expense ratios
@app.route("/compare", methods=["POST"])
def compare():
    scheme_ids = request.json.get("scheme_ids", [])
    schemes = get_all_schemes()
    scheme_names = [schemes.get(int(id), f"Scheme {id}") for id in scheme_ids]

    if len(scheme_ids) < 2:
        return jsonify({"error": "Please select at least 2 schemes"}), 400

    # Get expense ratios for each scheme
    expense_ratios = {str(id): get_expense_ratio(id) for id in scheme_ids}
    time.sleep(0.5)  # Rate limiting

    heatmap_img = create_heatmap(scheme_ids, scheme_names)
    return jsonify(
        {
            "heatmap": heatmap_img,
            "scheme_names": scheme_names,
            "expense_ratios": expense_ratios,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
