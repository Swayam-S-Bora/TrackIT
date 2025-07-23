# TrackIT - Price Tracking and Comparison Tool

**TrackIT** is a comprehensive web application designed to simplify and enhance the online shopping experience. It provides users with automated tools to track price changes, compare prices across major e-commerce platforms, predict future price trends, and receive real-time alerts for price drops.

## Overview

Online shoppers often struggle to monitor price fluctuations and determine the best time to make a purchase. TrackIT addresses these challenges by offering a unified platform for:

- Tracking product price history
- Comparing prices across different platforms (like Amazon and Flipkart)
- Predicting future price trends using historical data
- Alerting users when price drops occur

## Objective

To develop a web-based solution that:

- Tracks price changes of products over time
- Compares prices across multiple e-commerce websites
- Predicts future price movements using machine learning
- Notifies users about significant price drops via email and on-site alerts

## Key Features

- **Price Tracking**: Historical price data is tracked and stored.
- **Price Comparison**: See which platform (e.g., Amazon, Flipkart) offers the lowest price.
- **Price Prediction**: Uses logistic regression and past data to predict future prices.
- **Alerts**: Users receive notifications via email and dashboard alerts for price drops.
- **User-Friendly Interface**: A clean web interface for managing and viewing tracked products.

## Tech Stack

- **Backend**: Flask
- **Frontend**: HTML, CSS
- **Database**: SQLite3
- **Web Scraping**: Selenium
- **Prediction Models**: Scikit-learn, NumPy, Logistic Regression
- **Email Alerts**: SMTP (Simple Mail Transfer Protocol)

## Project Structure

```
TrackIT/
├── app.py              # Main Flask application
├── functions.py        # Utility functions for scraping and data processing
├── predictor.py        # Module for price prediction logic
├── requirements.txt    # Python dependencies
├── static/             # Static files (CSS, images)
│   ├── css/
│   └── js/
├── templates/          # HTML templates
│   ├── index.html
│   ├── results.html
│   └── layout.html
└── README.md           # Project documentation
```

## Step-by-Step Functionality

1. **User Registration & Login**: Secure authentication system with signup/login.
2. **Product Search & Tracking**: Users can input product URLs from supported websites.
3. **Web Scraping & Data Storage**: Automated scraping stores price data over time.
4. **Price Comparison**: Compare same product across e-commerce platforms.
5. **Price Prediction**: ML models analyze historical data to forecast trends.
6. **Price Drop Alerts**: Users are notified via email and website when drops are detected.
7. **Dashboard**: Overview of tracked products, price trends, and current prices.
8. **Manual Price Check**: Admins can manually trigger system-wide price updates.
9. **Database Management**:
   - `amazon_data`, `flipkart_data` tables for historical prices
   - `users_cart`, `users.db` for user data and preferences

## Interface Pages

- **Home Page**: Search for products, view trending items.
- **Search Results Page**: Cross-platform price comparison.
- **Product Page**: Detailed view with price history and tracking options.
- **Dashboard**: Personalized user dashboard with watchlist and alert management.

## Outcome

TrackIT offers a one-stop solution for online shoppers, enhancing purchase decisions by providing real-time data, trends, and alerts. The application aims to make e-commerce smarter and more efficient.


























