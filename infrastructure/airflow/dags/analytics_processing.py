"""
AuraLink Apache Airflow DAG - Analytics Processing
Phase 7: Batch processing for analytics, reporting, and data aggregation
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import logging

# Default arguments for DAG
default_args = {
    'owner': 'auralink',
    'depends_on_past': False,
    'email': ['ops@auralinkrtc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}

# Create DAG
dag = DAG(
    'analytics_processing',
    default_args=default_args,
    description='Process and aggregate analytics data for organizations',
    schedule_interval='0 2 * * *',  # Run daily at 2 AM
    start_date=datetime(2025, 10, 16),
    catchup=False,
    tags=['analytics', 'phase7', 'batch'],
)

def refresh_materialized_views(**context):
    """Refresh materialized views for analytics"""
    logging.info("Refreshing materialized views...")
    
    postgres_hook = PostgresHook(postgres_conn_id='auralink_db')
    
    try:
        # Refresh organization analytics summary
        postgres_hook.run("REFRESH MATERIALIZED VIEW CONCURRENTLY organization_analytics_summary;")
        logging.info("✓ Refreshed organization_analytics_summary")
        
        # Refresh daily usage summary
        postgres_hook.run("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_usage_summary;")
        logging.info("✓ Refreshed daily_usage_summary")
        
        logging.info("All materialized views refreshed successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to refresh materialized views: {e}")
        raise

def calculate_ai_costs(**context):
    """Calculate AI usage costs for all organizations"""
    logging.info("Calculating AI costs...")
    
    postgres_hook = PostgresHook(postgres_conn_id='auralink_db')
    execution_date = context['execution_date']
    
    # Query AI usage and calculate costs
    query = f"""
    INSERT INTO usage_records (
        record_id, organization_id, usage_type, quantity,
        unit_price_usd, total_cost_usd, billing_period_start,
        billing_period_end, recorded_at
    )
    SELECT
        gen_random_uuid(),
        organization_id,
        'ai_' || feature_type AS usage_type,
        COUNT(*) AS quantity,
        AVG(cost_usd) AS unit_price_usd,
        SUM(cost_usd) AS total_cost_usd,
        DATE('{execution_date.strftime('%Y-%m-%d')}'),
        DATE('{execution_date.strftime('%Y-%m-%d')}'),
        NOW()
    FROM ai_usage_analytics
    WHERE DATE(used_at) = DATE('{execution_date.strftime('%Y-%m-%d')}')
    AND organization_id IS NOT NULL
    GROUP BY organization_id, feature_type;
    """
    
    try:
        result = postgres_hook.run(query)
        logging.info(f"✓ Calculated AI costs for {execution_date}")
        return True
    except Exception as e:
        logging.error(f"Failed to calculate AI costs: {e}")
        raise

def generate_cost_insights(**context):
    """Generate cost optimization insights for organizations"""
    logging.info("Generating cost optimization insights...")
    
    postgres_hook = PostgresHook(postgres_conn_id='auralink_db')
    
    # Identify high AI usage organizations
    query = """
    INSERT INTO cost_optimization_insights (
        insight_id, organization_id, insight_type, severity,
        current_cost_monthly_usd, potential_savings_monthly_usd,
        savings_percentage, title, description, recommendations
    )
    SELECT
        gen_random_uuid(),
        organization_id,
        'high_ai_usage',
        CASE
            WHEN SUM(cost_usd) > 500 THEN 'high'
            WHEN SUM(cost_usd) > 200 THEN 'medium'
            ELSE 'low'
        END,
        SUM(cost_usd) * 30 AS monthly_cost,
        SUM(cost_usd) * 30 * 0.2 AS potential_savings,
        20.0,
        'High AI API Usage Detected',
        'Your organization is using AI features extensively. Consider optimizing usage or upgrading to a higher tier plan.',
        ARRAY['Review AI agent configurations', 'Enable caching for repeated queries', 'Consider BYOK for cost savings']
    FROM ai_usage_analytics
    WHERE used_at >= NOW() - INTERVAL '30 days'
    AND organization_id IS NOT NULL
    GROUP BY organization_id
    HAVING SUM(cost_usd) > 100
    ON CONFLICT DO NOTHING;
    """
    
    try:
        postgres_hook.run(query)
        logging.info("✓ Generated cost optimization insights")
        return True
    except Exception as e:
        logging.error(f"Failed to generate insights: {e}")
        raise

def archive_old_audit_logs(**context):
    """Archive audit logs older than retention period"""
    logging.info("Archiving old audit logs...")
    
    postgres_hook = PostgresHook(postgres_conn_id='auralink_db')
    
    try:
        # Call database function to archive logs
        result = postgres_hook.get_first("SELECT archive_old_audit_logs(90);")
        deleted_count = result[0] if result else 0
        
        logging.info(f"✓ Archived {deleted_count} audit log entries")
        return deleted_count
    except Exception as e:
        logging.error(f"Failed to archive audit logs: {e}")
        raise

def process_compliance_requests(**context):
    """Process pending compliance requests (GDPR data exports/deletions)"""
    logging.info("Processing compliance requests...")
    
    postgres_hook = PostgresHook(postgres_conn_id='auralink_db')
    
    # Get pending data export requests
    query = """
    SELECT request_id, user_id, export_format
    FROM compliance_requests
    WHERE request_type = 'data_export'
    AND status = 'pending'
    LIMIT 10;
    """
    
    try:
        requests = postgres_hook.get_records(query)
        
        for request in requests:
            request_id, user_id, export_format = request
            logging.info(f"Processing data export for user {user_id} (format: {export_format})")
            
            # TODO: Generate actual data export
            # For now, just update status
            update_query = f"""
            UPDATE compliance_requests
            SET status = 'processing',
                processing_notes = 'Export job started'
            WHERE request_id = '{request_id}';
            """
            postgres_hook.run(update_query)
        
        logging.info(f"✓ Processed {len(requests)} compliance requests")
        return len(requests)
    except Exception as e:
        logging.error(f"Failed to process compliance requests: {e}")
        raise

# Define tasks
task_refresh_views = PythonOperator(
    task_id='refresh_materialized_views',
    python_callable=refresh_materialized_views,
    dag=dag,
)

task_calculate_costs = PythonOperator(
    task_id='calculate_ai_costs',
    python_callable=calculate_ai_costs,
    dag=dag,
)

task_generate_insights = PythonOperator(
    task_id='generate_cost_insights',
    python_callable=generate_cost_insights,
    dag=dag,
)

task_archive_logs = PythonOperator(
    task_id='archive_audit_logs',
    python_callable=archive_old_audit_logs,
    dag=dag,
)

task_compliance = PythonOperator(
    task_id='process_compliance_requests',
    python_callable=process_compliance_requests,
    dag=dag,
)

# Define task dependencies
task_refresh_views >> [task_calculate_costs, task_generate_insights]
task_calculate_costs >> task_generate_insights
[task_archive_logs, task_compliance]  # These run independently
