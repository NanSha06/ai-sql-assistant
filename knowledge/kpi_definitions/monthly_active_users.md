# Monthly Active Users (MAU)

Count of distinct customers who placed at least one order within a calendar month.

SQL: SELECT COUNT(DISTINCT customer_id) FROM orders
     WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)