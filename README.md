# Intellectiva OASA Demo

A comprehensive full-stack project combining machine learning-powered metro ridership forecasting with an interactive web-based simulation and visualization platform for the Athens Metro (OASA) system.

## Project Overview

This project demonstrates an end-to-end intelligent transportation system that:
- **Predicts** metro passenger demand using machine learning models trained on historical ridership and weather open data
- **Simulates** metro operations with real-time scheduling optimization and passenger flow
- **Visualizes** metro network performance and provides decision support tools for transport planners

The project is split into two main components:

## Project Structure

### 1. **regression_model/** - Machine Learning Pipeline

A complete data engineering and ML pipeline for forecasting passenger validations on Athens Metro Line C.

**Technologies:**
- **Python 3.x**
- **Data Processing:** Pandas, NumPy, Scikit-learn
- **ML Models:** CatBoost, scikit-learn regression
- **Data Visualization:** Matplotlib, Plotly
- **Weather Data:** Real-time hourly weather integration
- **Big Data:** PySpark for large-scale data processing

**Key Components:**

| Module | Purpose |
|--------|---------|
| `fetchoasa.py` | Fetches OASA ridership data (embarking/disembarking validations) |
| `fetchweather.py` | Downloads hourly Athens weather data (2020-2025) |
| `merge_weather_oasa.py` | Enriches ridership data with weather features via timestamp alignment |
| `add_features.py` | Engineers temporal and contextual features (hour, day-of-week, holidays, etc.) |
| `train_model.py` | Trains regression models to forecast passenger demand |
| `optimizer.py` | Optimizes scheduling strategies using model predictions |
| `predict.py` | Generates predictions for new data |
| `validate.py` | Evaluates model performance on test sets |
| `plot.py` | Creates visualizations and performance reports |

**Data Flow:**
```
OASA API → Raw Ridership Data
         ↓
Weather API → Weather Data
         ↓
Merge & Clean → Enriched Dataset
         ↓
Feature Engineering → ML Features
         ↓
Train Model → Predictive Model
         ↓
Predictions & Optimization
```

---

### 2. **intelligent-metro-simulation/** - Interactive Web Platform

A Next.js-based real-time metro simulation and visualization dashboard with scheduling optimization.

**Technologies:**
- **Frontend Framework:** Next.js 16.0.3 (React 19)
- **Styling:** Tailwind CSS 4, PostCSS
- **UI Components:** Lucide React (icons)
- **Language:** TypeScript 5
- **Linting:** ESLint

**Key Features:**

| Feature | Description |
|---------|-------------|
| **Metro Map Visualization** | Interactive visual representation of Athens Metro Line C with all stations |
| **Real-time Simulation** | Live simulation of train movements and passenger flow dynamics |
| **Schedule Optimization** | Dual scheduling modes: Official OASA schedule vs. AI-optimized timetables |
| **Performance Metrics** | Real-time KPIs including wait times, occupancy rates, passenger satisfaction |
| **Demand Forecasting** | Integration with ML model predictions for passenger demand patterns |
| **Multi-page Interface** | Main dashboard, calculation views, citizen-focused interface |

**Key Components:**

| File | Purpose |
|------|---------|
| `app/page.tsx` | Main simulation engine with OASA data integration and scheduling logic |
| `components/metroMap.tsx` | Metro network visualization component |
| `libs/generateTimetable.ts` | Official and optimized schedule generation |
| `libs/costModel.ts` | Fare and cost calculation model |
| `libs/constants.ts` | Configuration constants (simulation date, station data) |
| `hooks/helperFunctions.ts` | Utility functions (Greek text normalization, time conversions) |
| `types/main.ts` | TypeScript interfaces for trains, trips, passengers, metrics |

**Pages:**
- `/` - Main simulation dashboard
- `/calc/` - Calculation and analysis view
- `/citizen-calc/` - Citizen-focused calculations and metrics

---

## Getting Started

### Prerequisites
- **Node.js 18+** (for web platform)
- **Python 3.8+** (for ML pipeline)

### Installation

#### ML Pipeline Setup
```bash
cd regression_model
pip install -r requirements.txt
```

#### Web Platform Setup
```bash
cd intelligent-metro-simulation
npm install
```

### Running the Project

#### Development - Web Platform
```bash
cd intelligent-metro-simulation
npm run dev
```
Open [http://localhost:3000](http://localhost:3000)

#### ML Pipeline - Training
```bash
cd regression_model
python train_model.py
```

#### ML Pipeline - Prediction
```bash
python predict.py
```

---

## Technology Stack

### Backend / Data Layer
- **Python 3.x** - Core data processing language
- **Pandas** - Data manipulation and analysis
- **NumPy** - Numerical computing
- **Scikit-learn** - ML algorithms and preprocessing
- **CatBoost** - Gradient boosting for regression
- **PySpark** - Distributed data processing
- **Requests** - HTTP client for API integration
- **Matplotlib & Plotly** - Data visualization

### Frontend
- **Next.js 16** - React framework with server-side rendering
- **React 19** - UI component library
- **TypeScript 5** - Type-safe JavaScript
- **Tailwind CSS 4** - Utility-first styling
- **Lucide React** - Icon library

### DevTools
- **ESLint** - Code linting
- **PostCSS** - CSS transformation

---

## Data Pipeline

The project uses real OASA (Athens Metro) ridership data enriched with weather information:

1. **Data Collection** - Fetches historical validations and hourly weather
2. **Data Enrichment** - Merges ridership with weather features by timestamp
3. **Feature Engineering** - Extracts temporal patterns (hour, day, holidays)
4. **Model Training** - Trains regression models on enriched dataset
5. **Prediction & Optimization** - Generates demand forecasts and optimizes schedules
6. **Simulation** - Uses predictions in real-time web-based simulation
7. **Visualization** - Displays results in interactive dashboard

---

## Use Cases

- **Transport Planners** - Analyze and optimize metro scheduling
- **Capacity Planning** - Forecast demand to plan train deployments
- **Research** - ML model training and validation on transit data
- **Citizens** - View real-time metro information and estimated wait times

---

## Notes

- The project focuses on **Athens Metro Line C** for demonstration
- Simulation date: Configurable (default: 2025-11-09)
- All station names are in Greek, with internal IDs (s01-s24+)
- Weather data spans 2020-2025 for comprehensive historical analysis

---

## License

Part of the Apps4Athens Hackathon 2.0 submission.
