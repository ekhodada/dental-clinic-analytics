-- Money displayed in CAD dollars; calculations aggregate integer cents first.
-- Aggregate payments and treatments separately: joining both raw facts multiplies totals.
-- I total service charges once per invoice before matching payments.
CREATE VIEW invoice_totals AS
SELECT "Invoice ID","Appointment ID",SUM(CAST(ROUND("Net Charge"*100) AS INTEGER)) cents
FROM treatments GROUP BY "Invoice ID","Appointment ID";

-- I match each invoice to its receipts without multiplying service lines.
CREATE VIEW unpaid_invoices AS
SELECT i."Invoice ID",i."Appointment ID",a."Patient ID",a."Location ID",
 substr(a."Scheduled Start",1,10) "Bill Date",i.cents/100.0 "Bill Amount",
 COALESCE(p.cents,0)/100.0 "Paid So Far",(i.cents-COALESCE(p.cents,0))/100.0 "Still Owed"
FROM invoice_totals i JOIN appointments a USING("Appointment ID") LEFT JOIN
 (SELECT "Invoice ID",SUM(CAST(ROUND("Amount"*100) AS INTEGER)) cents FROM payments GROUP BY "Invoice ID") p USING("Invoice ID");

-- I spread period costs over calendar days while preserving every cent.
CREATE VIEW daily_costs AS
WITH amounts AS (
 SELECT e.*,CAST(ROUND(e."Amount"*100) AS INTEGER) cents,
 CAST(julianday("Cost To")-julianday("Cost From")+1 AS INTEGER) days FROM expenses e
)
SELECT e."Expense ID",e."Location ID",d."Date",
 CAST(e.cents/e.days AS INTEGER)+CASE WHEN julianday(d."Date")-julianday(e."Cost From")<e.cents%e.days THEN 1 ELSE 0 END cents
FROM amounts e JOIN dates d ON d."Date" BETWEEN e."Cost From" AND e."Cost To";

-- I report branch revenue, receipts, costs and profit by reporting week.
CREATE VIEW weekly_finances AS
WITH revenue AS (
 SELECT a."Location ID",d."Week Starting",SUM(i.cents) cents FROM invoice_totals i
 JOIN appointments a USING("Appointment ID") JOIN dates d ON d."Date"=substr(a."Scheduled Start",1,10)
 GROUP BY a."Location ID",d."Week Starting"
), receipts AS (
 SELECT a."Location ID",d."Week Starting",SUM(CAST(ROUND(p."Amount"*100) AS INTEGER)) cents
 FROM payments p JOIN invoice_totals i USING("Invoice ID") JOIN appointments a USING("Appointment ID")
 JOIN dates d ON d."Date"=p."Payment Date" GROUP BY a."Location ID",d."Week Starting"
), costs AS (
 SELECT c."Location ID",d."Week Starting",SUM(c.cents) cents FROM daily_costs c JOIN dates d USING("Date") GROUP BY c."Location ID",d."Week Starting"
), weeks AS (SELECT "Week Starting",COUNT(*) days FROM dates GROUP BY "Week Starting")
SELECT w."Week Starting",l."Location ID",w.days "Days Included",CASE WHEN w.days=7 THEN 'Full week' ELSE 'Partial week' END "Week Coverage",
 COALESCE(r.cents,0)/100.0 "Service Revenue",COALESCE(p.cents,0)/100.0 "Money Received",
 COALESCE(c.cents,0)/100.0 "Operating Costs",(COALESCE(r.cents,0)-COALESCE(c.cents,0))/100.0 "Operating Profit",
 CASE WHEN r.cents>0 THEN ROUND(1.0*(r.cents-COALESCE(c.cents,0))/r.cents,6) END "Profit Margin"
FROM weeks w CROSS JOIN locations l
LEFT JOIN revenue r ON r."Location ID"=l."Location ID" AND r."Week Starting"=w."Week Starting"
LEFT JOIN receipts p ON p."Location ID"=l."Location ID" AND p."Week Starting"=w."Week Starting"
LEFT JOIN costs c ON c."Location ID"=l."Location ID" AND c."Week Starting"=w."Week Starting";

-- I count monthly patients and booking outcomes for each branch.
CREATE VIEW patient_trends AS
SELECT substr(a."Scheduled Start",1,7) "Month",a."Location ID",
 COUNT(DISTINCT CASE WHEN a."Status"='Completed' THEN a."Patient ID" END) "Patients Seen",
 SUM(a."Status"='Completed') "Completed Visits",
 COUNT(DISTINCT CASE WHEN a."Status"='Completed' AND substr(p."First Visit",1,7)=substr(a."Scheduled Start",1,7) THEN a."Patient ID" END) "New Patients",
 COUNT(DISTINCT CASE WHEN a."Status"='Completed' AND substr(p."First Visit",1,7)<substr(a."Scheduled Start",1,7) THEN a."Patient ID" END) "Returning Patients",
 SUM(a."Status"='No-show') "Missed Appointments",SUM(a."Status"='Cancelled') "Cancelled Appointments",
 SUM(a."Status"='Cancelled' AND (julianday(a."Scheduled Start")-julianday(a."Cancelled At"))*24<24) "Late Cancellations",
 ROUND(1.0*SUM(a."Status"='Completed')/NULLIF(SUM(a."Status" IN ('Completed','No-show')),0),6) "Attendance Rate"
FROM appointments a JOIN patients p USING("Patient ID") GROUP BY "Month",a."Location ID";

-- I summarize completed services and revenue by month, branch and care category.
CREATE VIEW care_summary AS
SELECT substr(a."Scheduled Start",1,7) "Month",a."Location ID",t."Care Category",
 COUNT(DISTINCT a."Patient ID") "Patients Treated",COUNT(*) "Services Completed",
 SUM(CAST(ROUND(t."Net Charge"*100) AS INTEGER))/100.0 "Service Revenue"
FROM treatments t JOIN appointments a USING("Appointment ID") GROUP BY "Month",a."Location ID",t."Care Category";

-- I compare reserved and actual treatment minutes with available clinical time.
CREATE VIEW capacity AS
WITH available AS (
 SELECT substr("Work Starts",1,7) "Month","Location ID",SUM("Available Minutes") minutes FROM availability GROUP BY "Month","Location ID"
), used AS (
 SELECT substr("Scheduled Start",1,7) "Month","Location ID",
 SUM(ROUND((julianday("Chair Available At")-julianday("Scheduled Start"))*1440)) booked,
 SUM(CASE WHEN "Status"='Completed' THEN ROUND((julianday("Treatment Finished")-julianday("Treatment Started"))*1440) ELSE 0 END) treated
 FROM appointments GROUP BY "Month","Location ID"
)
SELECT a."Month",a."Location ID",a.minutes "Available Minutes",u.booked "Reserved Minutes",u.treated "Treatment Minutes",
 ROUND(1.0*u.booked/a.minutes,6) "Booked Capacity",ROUND(1.0*u.treated/a.minutes,6) "Treatment Use"
FROM available a LEFT JOIN used u USING("Month","Location ID");

-- I assess each patient's latest recall plan at each month-end.
CREATE VIEW recall_trends AS
WITH months AS (SELECT "Month",MAX("Date") cutoff FROM dates GROUP BY "Month"), ranked AS (
 SELECT m."Month",m.cutoff,q.*,a."Location ID",
 ROW_NUMBER() OVER(PARTITION BY m."Month",q."Patient ID" ORDER BY a."Scheduled Start" DESC,q."Recall ID" DESC) rn
 FROM months m JOIN recalls q JOIN appointments a ON a."Appointment ID"=q."Previous Visit ID"
 WHERE substr(a."Scheduled Start",1,10)<=m.cutoff
)
SELECT "Month","Location ID",COUNT(*) "Patients With Recall Plan",
 SUM(date("Return Due",'+'||"Grace Days"||' days')<cutoff) "Overdue Patients",
 SUM("Return Due"<=cutoff AND date("Return Due",'+'||"Grace Days"||' days')>=cutoff) "Due Within Grace",
 SUM("Return Due">cutoff) "Not Yet Due"
FROM ranked WHERE rn=1 GROUP BY "Month","Location ID";

-- I split each category's revenue change into service volume and average-charge effects.
CREATE VIEW revenue_bridge AS
WITH annual AS (
 SELECT t."Care Category" care_category,
  substr(a."Scheduled Start",1,4) service_year, COUNT(*) services,
  SUM(CAST(ROUND(t."Net Charge"*100) AS INTEGER)) revenue_cents
 FROM treatments t JOIN appointments a USING("Appointment ID")
 WHERE a.Status='Completed' AND substr(a."Scheduled Start",1,4) IN ('2024','2025')
 GROUP BY 1,2
), comparison AS (
 SELECT care_category,
  SUM(CASE WHEN service_year='2024' THEN services ELSE 0 END) services_2024,
  SUM(CASE WHEN service_year='2025' THEN services ELSE 0 END) services_2025,
  SUM(CASE WHEN service_year='2024' THEN revenue_cents ELSE 0 END) cents_2024,
  SUM(CASE WHEN service_year='2025' THEN revenue_cents ELSE 0 END) cents_2025
 FROM annual GROUP BY care_category
), effects AS (
 SELECT *,1.0*cents_2024/NULLIF(services_2024,0) average_cents_2024,
  1.0*cents_2025/NULLIF(services_2025,0) average_cents_2025
 FROM comparison
), amounts AS (
 SELECT care_category,services_2024,services_2025,
  cents_2024/100.0 net_revenue_2024_cad,cents_2025/100.0 net_revenue_2025_cad,
  ROUND(average_cents_2024/100.0,4) average_charge_2024_cad,
  ROUND(average_cents_2025/100.0,4) average_charge_2025_cad,
  (cents_2025-cents_2024)/100.0 revenue_change_cad,
  ROUND((services_2025-services_2024)*average_cents_2024/100.0,2) volume_effect_cad,
  ROUND((average_cents_2025-average_cents_2024)*services_2025/100.0,2) price_effect_cad
 FROM effects
)
SELECT *,ROUND(revenue_change_cad-volume_effect_cad-price_effect_cad,2) rounding_difference_cad
FROM amounts ORDER BY care_category;

-- I compare branch no-show rates by whole days between booking and planned care.
CREATE VIEW noshow_by_lead_time AS
WITH bookings AS (
 SELECT a.*,CAST(julianday("Scheduled Start")-julianday("Booked At") AS INTEGER) lead_days
 FROM appointments a WHERE substr("Scheduled Start",1,4)='2025'
), bands AS (
 SELECT *,CASE WHEN lead_days<=6 THEN '0-6 days'
  WHEN lead_days<=29 THEN '7-29 days' ELSE '30+ days' END lead_time_band,
  CASE WHEN lead_days<=6 THEN 1 WHEN lead_days<=29 THEN 2 ELSE 3 END band_order
 FROM bookings
)
SELECT l."Location Name" branch,b.lead_time_band,COUNT(*) scheduled_appointments,
 SUM(b.Status='Completed') completed_visits,SUM(b.Status='No-show') no_shows,
 SUM(b.Status='Cancelled') cancelled_appointments,
 SUM(b.Status IN ('Completed','No-show')) eligible_appointments,
 1.0*SUM(b.Status='No-show')/NULLIF(SUM(b.Status IN ('Completed','No-show')),0) no_show_rate
FROM bands b JOIN locations l USING("Location ID")
GROUP BY l."Location ID",b.lead_time_band,b.band_order ORDER BY l."Location ID",b.band_order;

-- I age unpaid invoices at December 31, 2025 using only receipts known by that date.
CREATE VIEW receivables_by_age AS
WITH bands(band_order,invoice_age_band,minimum_days,maximum_days) AS (
 VALUES (1,'0-30 days',0,30),(2,'31-90 days',31,90),(3,'91-180 days',91,180),
  (4,'181-365 days',181,365),(5,'366+ days',366,999999)
), paid AS (
 SELECT "Invoice ID",SUM(CAST(ROUND(Amount*100) AS INTEGER)) cents
 FROM payments WHERE "Payment Date"<='2025-12-31' GROUP BY "Invoice ID"
), balances AS (
 SELECT i."Invoice ID",i.cents-COALESCE(p.cents,0) unpaid_cents,
  CAST(julianday('2025-12-31')-julianday(substr(a."Scheduled Start",1,10)) AS INTEGER) age_days
 FROM invoice_totals i JOIN appointments a USING("Appointment ID")
 LEFT JOIN paid p USING("Invoice ID") WHERE substr(a."Scheduled Start",1,10)<='2025-12-31'
)
SELECT '2025-12-31' as_of_date,b.invoice_age_band,COUNT(x."Invoice ID") unpaid_invoices,
 COALESCE(SUM(x.unpaid_cents),0)/100.0 unpaid_balance_cad
FROM bands b LEFT JOIN balances x ON x.age_days BETWEEN b.minimum_days AND b.maximum_days
 AND x.unpaid_cents>0 GROUP BY b.band_order,b.invoice_age_band ORDER BY b.band_order;

-- I divide whole-visit revenue by actual hours, assigning each visit to its primary category.
CREATE VIEW revenue_per_chair_hour AS
WITH service_counts AS (
 SELECT "Appointment ID",COUNT(*) services FROM treatments GROUP BY "Appointment ID"
), visits AS (
 SELECT a."Care Category" care_category,i.cents revenue_cents,s.services,
  CAST(ROUND((julianday(a."Treatment Finished")-julianday(a."Treatment Started"))*1440) AS INTEGER) treatment_minutes
 FROM appointments a JOIN invoice_totals i USING("Appointment ID")
 JOIN service_counts s USING("Appointment ID")
 WHERE a.Status='Completed' AND substr(a."Scheduled Start",1,4)='2025'
)
SELECT care_category,SUM(services) services,COUNT(*) completed_visits,
 SUM(revenue_cents)/100.0 net_revenue_cad,SUM(treatment_minutes)/60.0 actual_treatment_hours,
 ROUND(SUM(revenue_cents)*0.6/NULLIF(SUM(treatment_minutes),0),2) revenue_per_chair_hour_cad
FROM visits GROUP BY care_category ORDER BY care_category;

-- I prepare one patient record with observable follow-up windows and completed-care revenue.
CREATE VIEW patient_followup AS
WITH observation AS (
 SELECT MIN(Date) first_observed_date,MAX(Date) last_observed_date FROM dates
), windows AS (
 SELECT p.*,o.first_observed_date,o.last_observed_date,
  MIN(date(p."First Visit",'+6 months'),date(p."First Visit",'start of month','+7 months','-1 day')) six_month_end,
  MIN(date(p."First Visit",'+12 months'),date(p."First Visit",'start of month','+13 months','-1 day')) twelve_month_end
 FROM patients p CROSS JOIN observation o
), history AS (
 SELECT p."Patient ID" patient_id,p."How They Found Us" channel,p."First Visit" first_visit_date,
  p.first_observed_date,p.last_observed_date,p.six_month_end,p.twelve_month_end,
  MAX(CASE WHEN substr(a."Scheduled Start",1,10)=p."First Visit" THEN 1 ELSE 0 END) observed_first_visit,
  MAX(CASE WHEN substr(a."Scheduled Start",1,10)>p."First Visit"
   AND substr(a."Scheduled Start",1,10)<=p.six_month_end THEN 1 ELSE 0 END) returned_6_months,
  MAX(CASE WHEN substr(a."Scheduled Start",1,10)>p."First Visit"
   AND substr(a."Scheduled Start",1,10)<=p.twelve_month_end THEN 1 ELSE 0 END) returned_12_months,
  COALESCE(SUM(i.cents),0) revenue_cents,
  COALESCE(SUM(CASE WHEN substr(a."Scheduled Start",1,10) BETWEEN p."First Visit" AND p.twelve_month_end
   THEN i.cents ELSE 0 END),0) first_12_month_revenue_cents
 FROM windows p LEFT JOIN appointments a ON a."Patient ID"=p."Patient ID" AND a.Status='Completed'
 LEFT JOIN invoice_totals i USING("Appointment ID") GROUP BY p."Patient ID"
)
SELECT *,CASE WHEN observed_first_visit=1 AND first_visit_date>=first_observed_date
 AND six_month_end<=last_observed_date THEN 1 ELSE 0 END eligible_6_months,
 CASE WHEN observed_first_visit=1 AND first_visit_date>=first_observed_date
 AND twelve_month_end<=last_observed_date THEN 1 ELSE 0 END eligible_12_months
FROM history;

-- I compare acquisition channels using eligible return rates and revenue per registered patient.
CREATE VIEW channel_value AS
SELECT channel,COUNT(*) patients,SUM(eligible_12_months) eligible_12_month_patients,
 SUM(eligible_12_months*returned_12_months) returned_12_month_patients,
 1.0*SUM(eligible_12_months*returned_12_months)/NULLIF(SUM(eligible_12_months),0) return_rate_12_months,
 SUM(revenue_cents)/100.0 net_revenue_cad,ROUND(SUM(revenue_cents)/100.0/COUNT(*),2) revenue_per_patient_cad,
 ROUND(SUM(CASE WHEN eligible_12_months=1 THEN first_12_month_revenue_cents ELSE 0 END)/100.0/
  NULLIF(SUM(eligible_12_months),0),2) first_12_month_revenue_per_eligible_patient_cad
FROM patient_followup GROUP BY channel ORDER BY channel;

-- I compare first-visit quarters without counting incomplete follow-up windows as failures.
CREATE VIEW retention_cohorts AS
SELECT substr(first_visit_date,1,4)||'-Q'||CAST((CAST(substr(first_visit_date,6,2) AS INTEGER)+2)/3 AS INTEGER) first_visit_quarter,
 COUNT(*) patients,SUM(eligible_6_months) eligible_6_month_patients,
 SUM(eligible_6_months*returned_6_months) returned_6_month_patients,
 1.0*SUM(eligible_6_months*returned_6_months)/NULLIF(SUM(eligible_6_months),0) return_rate_6_months,
 SUM(eligible_12_months) eligible_12_month_patients,
 SUM(eligible_12_months*returned_12_months) returned_12_month_patients,
 1.0*SUM(eligible_12_months*returned_12_months)/NULLIF(SUM(eligible_12_months),0) return_rate_12_months
FROM patient_followup WHERE observed_first_visit=1 AND first_visit_date>=first_observed_date
GROUP BY first_visit_quarter ORDER BY first_visit_quarter;
