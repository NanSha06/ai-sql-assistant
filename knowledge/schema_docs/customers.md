# Table: customers

Stores all registered customers.

## Columns
- customer_id: integer, primary key
- name: varchar, customer full name
- email: varchar, unique email address
- created_at: timestamp, account creation date

## Common queries
- Count new customers by month
- Find customers by email
- Join with orders on customer_id