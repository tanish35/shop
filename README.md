# Store Uptime/Downtime Reporting System

A high-performance FastAPI application designed to analyze store activity data from a TimescaleDB database and generate detailed uptime/downtime reports. The system processes large-scale time-series data, intelligently interpolates status between sparse data points, and calculates metrics strictly within defined business hours.

## Key Features

- **Asynchronous Report Generation**: API endpoints to trigger and retrieve long-running report generation tasks without blocking the client.
- **Business-Hour Aware**: Accurately calculates uptime and downtime only within a store's specified local business hours.
- **Intelligent Data Interpolation**: Fills gaps in sparse polling data to provide a complete and logical view of a store's status over time.
- **High-Performance Database Interaction**: Built on Prisma Client Python for type-safe database access and optimized for large datasets with specific indexing strategies.
- **Scalable Architecture**: Leverages FastAPI for speed and TimescaleDB for efficient time-series data management.
- **CSV Output**: Generates a clean, user-friendly CSV report.

## Technology Stack

- **Backend**: FastAPI
- **Database**: TimescaleDB / PostgreSQL
- **ORM**: Prisma Client Python
- **Data Handling**: Pytz for timezone conversions
- **Environment**: Python 3.10+

## Prerequisites

- Python 3.10+ and Pip
- Node.js and npm (for running Prisma CLI commands)
- Access to a running PostgreSQL or TimescaleDB instance

---

## 1. Setup and Installation

### Step 1: Clone the Repository

```bash
git clone
cd
```

### Step 2: Set Up Python Environment

Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required Python packages.

```bash
pip install -r requirements.txt
```

### Step 3: Install Node.js Dependencies

Prisma Client Python uses Node.js for its command-line interface.

```bash
npm install
```

### Step 4: Configure Environment Variables

Create a `.env` file by copying the example file.

```bash
cp .env.example .env
```

Edit the `.env` file and set your `DATABASE_URL`. For long-running report generation tasks, it is crucial to include timeout parameters to avoid connection errors.

**Example `.env` content:**

```
# Example for a Timescale Cloud database
# pool_timeout=0 disables the connection pool timeout, essential for long jobs.
# connect_timeout=30 gives 30 seconds to establish a new connection.
DATABASE_URL="postgres://user:password@host:port/dbname?sslmode=require&pool_timeout=0&connect_timeout=30"
```

---

## 2. Database Setup and Optimization

This application requires the database tables to be created and populated. Due to the large volume of data, specific optimizations are necessary for the application to perform correctly.

### Step 1: Define the Schema

The database schema is defined in `prisma/schema.prisma`. Ensure this file reflects your desired table structures.

```prisma
// prisma/schema.prisma

model StoreStatus {
  store_id  String
  timestamp DateTime @map("timestamp_utc")
  status    String

  @@id([store_id, timestamp])
  @@index([store_id, timestamp]) // Composite index for performance
  @@map("store_status")
}

model StoreHours {
  store_id         String
  day_of_week      Int
  start_time_local String
  end_time_local   String

  @@id([store_id, day_of_week])
  @@map("store_hours")
}

model StoreTimezone {
  store_id     String  @id
  timezone_str String

  @@map("store_timezone")
}
```

### Step 2: Load Initial Data

The application assumes the three tables (`store_status`, `store_hours`, `store_timezone`) are already populated. For large CSV files, use a bulk-loading tool for efficiency.

**Example using `timescaledb-parallel-copy`:**

```bash
timescaledb-parallel-copy \
  --connection "YOUR_DATABASE_URL" \
  --table store_status \
  --file path/to/store_status.csv \
  --workers 4 \
  --copy-options "CSV,HEADER"
```

### Step 3: Apply Database Constraints and Indexes (CRITICAL)

To handle millions of rows and avoid `ReadTimeout` errors, you **must** apply primary keys and performance indexes directly in your database.

**1. Clean Up Duplicate Data**

Before adding primary keys, remove any duplicate entries. For example, to deduplicate `store_hours`:

```sql
WITH duplicates AS (
  SELECT
    ctid,
    ROW_NUMBER() OVER (
      PARTITION BY store_id, day_of_week
      ORDER BY ctid
    ) AS rn
  FROM store_hours
)
DELETE FROM store_hours
WHERE ctid IN (
  SELECT ctid
  FROM duplicates
  WHERE rn > 1
);
```

**2. Add Primary Keys**

```sql
-- For store_status (composite key)
ALTER TABLE store_status ADD PRIMARY KEY (store_id, timestamp_utc);

-- For store_hours (composite key)
ALTER TABLE store_hours ADD PRIMARY KEY (store_id, day_of_week);

-- For store_timezone
ALTER TABLE store_timezone ADD PRIMARY KEY (store_id);
```

**3. Create Performance Index**

This index is **essential** for the report generation query to run efficiently.

```sql
-- This composite index dramatically speeds up lookups by store and time.
CREATE INDEX IF NOT EXISTS idx_store_status_id_timestamp ON store_status (store_id, timestamp_utc DESC);
```

### Step 4: Generate the Prisma Client

After setting up the database and schema, generate the Prisma Client.

```bash
npx prisma generate
```

---

## 3. Running the Application

To start the FastAPI server, run the following command from the root directory:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

---

## 4. API Endpoints

### Trigger Report Generation

Starts a new report generation process in the background.

- **Endpoint**: `POST /trigger_report`
- **Success Response (202 Accepted)**:
  ```json
  {
    "report_id": "some_unique_report_id"
  }
  ```

### Get Report Status and Results

Retrieves the status of a report generation task. If complete, it provides a download link for the CSV file.

- **Endpoint**: `GET /get_report/{report_id}`
- **Responses**:
  - **If still running (202 Accepted)**:
    ```json
    {
      "status": "Running"
    }
    ```
  - **If complete (200 OK)**:
    The response will be a CSV file attachment.
  - **If not found (404 Not Found)**:
    ```json
    {
      "detail": "Report not found"
    }
    ```
