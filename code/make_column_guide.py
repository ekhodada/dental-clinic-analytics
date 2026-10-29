from clean_and_refresh import BASE,read,write
D={
 'Location ID':'Branch code: L1, L2 or L3.','Location Name':'Fictional branch name.','City':'Branch city.','Chairs':'Number of treatment chairs.',
 'Patient ID':'Anonymous patient code, shared across all branches.','Birth Year':'Birth year; age is approximate.','Gender':'Recorded gender, including not recorded.',
 'Home Location ID':'Usual branch; may differ from where the patient attends.','First Visit':'First-ever completed visit, including summarized earlier history.',
 'How They Found Us':'Simulated original referral or acquisition source.',
 'Session ID':'Working block used to match a booking to a provider and chair.','Provider ID':'Dentist D01-D06 or hygienist H01-H06.',
 'Provider Type':'Dentist or Hygienist.','Chair ID':'Branch-specific treatment chair.',
 'Work Starts':'Start of available clinical working block.','Work Ends':'End of available clinical working block.','Available Minutes':'Minutes available in that working block.',
 'Appointment ID':'One booking; can be completed, cancelled or missed.','Main Service':'Main service planned for the booking.',
 'Care Category':'One of six service reporting groups; not a diagnosis.',
 'Booked At':'When the booking was made.','Scheduled Start':'When treatment was planned to start.',
 'Scheduled End':'When treatment was planned to finish.','Chair Available At':'Planned finish plus 10 minutes for cleanup.',
 'Status':'Completed, Cancelled or No-show.','Cancelled At':'When the booking was cancelled; otherwise blank.',
 'Treatment Started':'Actual start for completed care; otherwise blank.','Treatment Finished':'Actual finish for completed care; otherwise blank.',
 'Treatment Record ID':'One completed billed service line, not a separate visit.','Invoice ID':'Bill reference; several services and payments can share it.',
 'Treatment':'Name of completed billed service.','Gross Charge':'Charge before deductions, CAD dollars.','Discount':'Discount deducted, CAD dollars.',
 'Adjustment':'Other charge reduction, CAD dollars; not a refund.','Net Charge':'Gross Charge minus Discount minus Adjustment, CAD dollars.',
 'Payment ID':'One receipt against a bill.','Payment Date':'Date money was received.','Paid By':'Patient or Insurer.',
 'Amount':'CAD dollars: receipt in payments, expense in expenses.',
 'Expense ID':'One cost record.','Cost Type':'Rent, wages, supplies or another operating expense.',
 'Cost From':'First day covered by the expense.','Cost To':'Last day covered by the expense.',
 'Paid On':'Assumed expense payment date; may be later than the cutoff; blank for depreciation.',
 'Cost Sharing':'Direct branch expense or explicit allocation of a shared cost.',
 'Recall ID':'One expected follow-up plan.','Previous Visit ID':'Completed hygiene visit that created this plan.',
 'Return Due':'Simulated date for the next follow-up.','Grace Days':'Extra days before the plan is considered overdue; not a clinical recommendation.',
 'Date':'Calendar day.','Week Starting':'Monday of this week.','Month':'Calendar month, YYYY-MM.'}
rows=[]
for p in sorted((BASE/'processed'/'clean').glob('*.csv')):
 fields,records=read(p)
 for field in fields:
  assert field in D,field
  rows.append({'Table':p.name,'Column':field,'Simple Meaning':D[field],'Example':records[0][field]})
write(BASE/'column_guide.csv',rows)
print(f'{len(rows)} column definitions across nine files.')
