# Pool-Analytics-Dashboard

![Dashboard Preview](docs/executive_summary.png)

## Executive Summary
An end-to-end analytics solution built to unify transactional data across facility management systems, POS software, and local weather history. By centralizing raw data from MemberSplash and Square into a structured cloud database (Supabase) via a Python ETL pipeline, this project delivers actionable operational intelligence to maximize pool attendance and concession revenue.

> **Note on data:** This is a public repository, so the underlying data has been synthetically regenerated to protect member and business privacy. The statistical relationships (correlations, seasonal trends, lift percentages) are preserved from the original analysis performed for a real regional swim club.

![Dashboard Demo](docs/powerbi.gif)

## Table of Contents
- [About This Project](#about-this-project)
- [Key Business Insights & Recommendations](#key-business-insights--recommendations)
- [Tech Stack & Architecture](#tech-stack--architecture)
- [Data Pipeline Architecture](#data-pipeline-architecture)
- [Power BI Data Model](#power-bi-data-model-star-schema)
- [Dashboard Visualizations](#dashboard-visualizations)
- [Repository Structure](#repository-structure)
- [How to Run Locally](#how-to-run-locally)
- [Future Improvements](#future-improvements)

## Key Business Insights & Recommendations
* **Check-ins Are the Strongest Predictor of Revenue (r = 0.83):** Statistical analysis revealed that facility check-ins are the strongest observed predictor of concession sales, outperforming pure weather metrics (e.g., temperature/heat index).
  * *Recommendation:* Focus marketing strategies on driving member & guest check-ins. Implement a "Loyalty Perk" (e.g., *Visit 10 times, get 15% off at the Snack Shack*) to incentivize repeat visits.
* **Food Truck Non-Cannibalization (+27% Attendance):** Historical event analysis showed that bringing external food trucks to the facility was associated with a **27% net increase in overall pool check-ins**, without cannibalizing native concession sales — yielding a net positive revenue impact.
  * *Recommendation:* Expand the number of food truck events given the sizable uptick in attendance, which drives both food truck sales and concession sales.
* **Inventory Stockout & Bundling Strategy:** Leveraged domain experience (lifeguard operations) alongside item-level sales distribution to identify consistent stockouts on top-selling concession items.
  * *Recommendation:* Expand capacity of top-selling items (soft pretzels) to meet current demand and reduce sales lost to stockouts.

## Tech Stack & Architecture

* **Data Extraction & Ingestion:** Manually extracted raw, unformatted CSV exports from **MemberSplash** (membership/check-ins) and **Square POS** (concessions).
* **ETL Pipeline (Python/Pandas):**
  * Cleaned messy text, standardized irregular time formats, and calculated derived fields.
  * Fetched historical hourly weather data via the **Open-Meteo API** (temperature, precipitation, wind speed, feels-like calculations).
  * Handled dynamic upserts directly to a **Supabase (PostgreSQL)** database.
* **Semantic Modeling & Visualization (Power BI):** Connected directly to Supabase to build a Star Schema model, complete with custom DAX time-intelligence measures (YoY seasonal growth).

## Data Pipeline Architecture
```
[ MemberSplash CSVs ] ──┐
[ Square POS CSVs   ] ──┼─> [ Python ETL Script ] ──> [ Open-Meteo API ]
                        │          │
                        │          v
                        └──> [ Supabase Postgres ] ──> [ Power BI Dashboard ]
```

## Power BI Data Model (Star Schema)

![Power BI Relational Model](docs/data_model_schema.png)

* **Star Schema Architecture:** Centered around three core transactional fact tables (`fact_membership_sales`, `fact_checkins`, `fact_concession_sales`) and an hourly log (`fact_weather`).
* **Conformed Dimensions:** Shared dimension tables (`dim_date`, `dim_hour`) filter multiple fact tables simultaneously via single-direction `1:*` relationships, ensuring strict data integrity and performant cross-filtering.
* **Dedicated Measure Table:** Implemented an isolated `_Measures` table to store all DAX calculations (YoY growth, moving averages, period comparisons) for clean model organization.

---

## Dashboard Visualizations

### 1. Executive Overview
![Executive Overview Page](docs/executive_summary.png)
*High-level summary of total revenue, daily check-in trends, and overall season performance.*

### 2. Concession & Inventory Performance
![Concession Performance Page](docs/concessions.png)
*Item-level sales distribution, category sales, and heat-index purchasing behaviors.*

### 3. Check-In & Attendance Analytics
![Check-In Analytics Page](docs/check_ins.png)
*Breakdown of peak hourly check-in volume, weather correlations, and YoY measures.*

### 4. Membership Sale Analysis
![Membership Sales Page](docs/membership_sales.png)
*Analyzes membership sales volume, seasonal growth trends, and revenue by membership category.*

---

## Repository Structure
```
Pool-Analytics-Dashboard/
├── docs/                  # Dashboard screenshots used in this README
├── src/                   # Python ETL scripts (extraction, cleaning, weather API, Supabase upserts)
├── requirements.txt       # Python dependencies
├── LICENSE
└── README.md
```
> Update the tree above to match your actual folder/file names before publishing.

## Tech Stack & Dependencies

* **Language:** Python 3.13
* **ETL Libraries:** `pandas`, `numpy`, `requests`, `python-dateutil`, `openpyxl`
* **Database & Storage:** Supabase (PostgreSQL), CSV
* **Business Intelligence:** Power BI Desktop (DAX, Power Query)

---

## How to Run Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/natey/Pool-Analytics-Dashboard.git
   cd Pool-Analytics-Dashboard
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the ETL pipeline:**
   ```bash
   python scripts/pool_data_etl_script.py
   ```

4. **Open the Power BI dashboard:**
   Open the `.pbix` file in Power BI Desktop and connect it to your own Supabase instance credentials.

## Future Improvements
- **Automate ingestion:** Replace manual CSV exports from MemberSplash/Square with a scheduled API pull or scraper to eliminate manual extraction steps.
- **Predictive modeling:** Layer in a forecasting model (e.g., attendance prediction based on weather + day-of-week) to move from descriptive to predictive analytics.
- **Real-time refresh:** Migrate from manual/scheduled Power BI refresh to a streaming or near-real-time pipeline for same-day operational decisions.

## About This Project
This project was built to analyze 4+ seasons of real attendance, sales, and weather data for a regional swim club, with findings and strategy recommendations presented directly to the club's executive board. Underlying data in this public repository has been synthetically regenerated to protect member and business privacy — statistical relationships (correlations, seasonal trends, lift percentages) are preserved from the original analysis.

Built by Nate Yohn — Information Systems & Analytics student at Shippensburg University.
📧 nate.m.yohn@gmail.com | [LinkedIn](https://www.linkedin.com/in/nate-yohn-54763524a/)

## License
This project is licensed under the MIT License — see the `LICENSE` file for details.
> Add a LICENSE file to the repo root (MIT is a common, permissive choice for portfolio projects) or swap this line for whichever license you choose.