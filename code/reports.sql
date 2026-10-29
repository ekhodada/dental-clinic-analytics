-- Money displayed in CAD dollars; calculations aggregate integer cents first.
-- Aggregate payments and treatments separately: joining both raw facts multiplies totals.
CREATE VIEW invoice_totals AS
SELECT "Invoice ID","Appointment ID",SUM(CAST(ROUND("Net Charge"*100) AS INTEGER)) cents
FROM treatments GROUP BY "Invoice ID","Appointment ID";

CREATE VIEW unpaid_invoices AS
SELECT i."Invoice ID",i."Appointment ID",a."Patient ID",a."Location ID",
 substr(a."Scheduled Start",1,10) "Bill Date",i.cents/100.0 "Bill Amount",
 COALESCE(p.cents,0)/100.0 "Paid So Far",(i.cents-COALESCE(p.cents,0))/100.0 "Still Owed"
FROM invoice_totals i JOIN appointments a USING("Appointment ID") LEFT JOIN
 (SELECT "Invoice ID",SUM(CAST(ROUND("Amount"*100) AS INTEGER)) cents FROM payments GROUP BY "Invoice ID") p USING("Invoice ID");

CREATE VIEW daily_costs AS
WITH amounts AS (
 SELECT e.*,CAST(ROUND(e."Amount"*100) AS INTEGER) cents,
 CAST(julianday("Cost To")-julianday("Cost From")+1 AS INTEGER) days FROM expenses e
)
SELECT e."Expense ID",e."Location ID",d."Date",
 CAST(e.cents/e.days AS INTEGER)+CASE WHEN julianday(d."Date")-julianday(e."Cost From")<e.cents%e.days THEN 1 ELSE 0 END cents
FROM amounts e JOIN dates d ON d."Date" BETWEEN e."Cost From" AND e."Cost To";

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

CREATE VIEW care_summary AS
SELECT substr(a."Scheduled Start",1,7) "Month",a."Location ID",t."Care Category",
 COUNT(DISTINCT a."Patient ID") "Patients Treated",COUNT(*) "Services Completed",
 SUM(CAST(ROUND(t."Net Charge"*100) AS INTEGER))/100.0 "Service Revenue"
FROM treatments t JOIN appointments a USING("Appointment ID") GROUP BY "Month",a."Location ID",t."Care Category";

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
