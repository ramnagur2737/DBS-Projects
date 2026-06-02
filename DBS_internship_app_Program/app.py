from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import mysql.connector
import os
from dotenv import load_dotenv

# Import utilities & blue prints
from utils.db import execute_query, execute_dml, call_procedure
from utils.cloudinary_utils import upload_resume
from routes.admin import admin_bp, login_required
from routes.upload_routes import upload_bp

load_dotenv()

app = Flask(__name__)

# Essential for session handling and flash messages
app.secret_key = os.getenv("SESSION_SECRET", "super-secret-key-for-internship-placement-tracking")

# Register Blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(upload_bp)

# =========================================================
# DASHBOARD / HOME ROUTE
# =========================================================
@app.route('/')
@app.route('/home')
@login_required
def dashboard():
    """Renders the admin stats dashboard, matching Screenshot 3."""
    # Query total counts
    total_students = execute_query("SELECT COUNT(*) AS count FROM student", fetch="one")['count']
    total_applications = execute_query("SELECT COUNT(*) AS count FROM job_application", fetch="one")['count']
    total_offers = execute_query("SELECT COUNT(*) AS count FROM offer_record", fetch="one")['count']
    total_companies = execute_query("SELECT COUNT(*) AS count FROM company", fetch="one")['count']
    total_roles = execute_query("SELECT COUNT(*) AS count FROM job_role", fetch="one")['count']

    # Placed students (count of distinct students who have accepted a full-time or internship offer)
    placed_students_q = execute_query(
        """
        SELECT COUNT(DISTINCT a.student_id) AS count 
        FROM job_application a 
        JOIN offer_record o ON a.application_id = o.application_id 
        WHERE o.offer_status = 'Accepted'
        """, fetch="one"
    )
    placed_students = placed_students_q['count'] if placed_students_q else 0

    # Highest package offered among accepted offers
    highest_package_q = execute_query(
        """
        SELECT MAX(r.package) AS max_pkg 
        FROM job_role r 
        JOIN job_application a ON r.role_id = a.role_id 
        JOIN offer_record o ON a.application_id = o.application_id 
        WHERE o.offer_status = 'Accepted'
        """, fetch="one"
    )
    highest_package = float(highest_package_q['max_pkg']) if highest_package_q and highest_package_q['max_pkg'] else 0.0

    # Average package offered among accepted offers
    average_package_q = execute_query(
        """
        SELECT AVG(r.package) AS avg_pkg 
        FROM job_role r 
        JOIN job_application a ON r.role_id = a.role_id 
        JOIN offer_record o ON a.application_id = o.application_id 
        WHERE o.offer_status = 'Accepted'
        """, fetch="one"
    )
    average_package = round(float(average_package_q['avg_pkg']), 2) if average_package_q and average_package_q['avg_pkg'] else 0.0

    stats = {
        'total_students': total_students,
        'total_applications': total_applications,
        'total_offers': total_offers,
        'placed_students': placed_students,
        'highest_package': highest_package,
        'average_package': average_package,
        'total_companies': total_companies,
        'total_roles': total_roles
    }

    return render_template('home.html', stats=stats)


# =========================================================
# STUDENT DETAILS CRUD
# =========================================================
@app.route('/students')
@login_required
def list_students():
    """Lists student records matching Screenshot 2, with optional search filter."""
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        query = """
            SELECT student_id, name, branch, cgpa, email, phone, academic_level, graduation_year, resume_url 
            FROM student 
            WHERE name LIKE %s OR branch LIKE %s
            ORDER BY student_id DESC
        """
        students = execute_query(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        query = """
            SELECT student_id, name, branch, cgpa, email, phone, academic_level, graduation_year, resume_url 
            FROM student 
            ORDER BY student_id DESC
        """
        students = execute_query(query)
        
    return render_template('student_details.html', students=students, search_query=search_query)


@app.route('/students/create', methods=['POST'])
@login_required
def create_student():
    """Handles adding a new student, uploading their resume directly to Cloudinary."""
    name = request.form.get('name', '').strip()
    branch = request.form.get('branch', '').strip()
    cgpa = request.form.get('cgpa', '0.0')
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    academic_level = request.form.get('academic_level', 'UG')
    graduation_year = request.form.get('graduation_year', '2026')
    
    resume_file = request.files.get('resume')
    resume_url = None
    resume_public_id = None
    
    if resume_file and resume_file.filename != '':
        try:
            upload_res = upload_resume(resume_file)
            resume_url = upload_res['url']
            resume_public_id = upload_res['public_id']
        except Exception as e:
            flash(f"Cloudinary Upload Failed: {str(e)}", "danger")
            return redirect(url_for('list_students'))

    try:
        execute_dml(
            """
            INSERT INTO student (name, branch, cgpa, email, phone, academic_level, graduation_year, resume_url, resume_public_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (name, branch, cgpa, email, phone, academic_level, graduation_year, resume_url, resume_public_id)
        )
        flash(f"Student record for '{name}' created successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_students'))


@app.route('/students/edit', methods=['POST'])
@login_required
def edit_student():
    """Handles updating student details, with optional resume re-uploading."""
    student_id = request.form.get('student_id')
    name = request.form.get('name', '').strip()
    branch = request.form.get('branch', '').strip()
    cgpa = request.form.get('cgpa', '0.0')
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    academic_level = request.form.get('academic_level', 'UG')
    graduation_year = request.form.get('graduation_year', '2026')
    
    resume_file = request.files.get('resume')
    
    try:
        if resume_file and resume_file.filename != '':
            # Upload new resume to Cloudinary
            upload_res = upload_resume(resume_file)
            execute_dml(
                """
                UPDATE student 
                SET name=%s, branch=%s, cgpa=%s, email=%s, phone=%s, academic_level=%s, graduation_year=%s, resume_url=%s, resume_public_id=%s
                WHERE student_id=%s
                """,
                (name, branch, cgpa, email, phone, academic_level, graduation_year, upload_res['url'], upload_res['public_id'], student_id)
            )
        else:
            # Update detail without replacing existing resume
            execute_dml(
                """
                UPDATE student 
                SET name=%s, branch=%s, cgpa=%s, email=%s, phone=%s, academic_level=%s, graduation_year=%s
                WHERE student_id=%s
                """,
                (name, branch, cgpa, email, phone, academic_level, graduation_year, student_id)
            )
        flash(f"Student details updated successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_students'))


@app.route('/students/delete/<int:student_id>')
@login_required
def delete_student(student_id):
    """Deletes a student record."""
    try:
        execute_dml("DELETE FROM student WHERE student_id = %s", (student_id,))
        flash("Student record deleted successfully.", "success")
    except mysql.connector.Error as err:
        # Standard foreign key restrict check
        flash(f"Deletion failed: {err.msg}", "danger")
    return redirect(url_for('list_students'))


# =========================================================
# COMPANY DETAILS CRUD
# =========================================================
@app.route('/companies')
@login_required
def list_companies():
    """Lists companies and aggregates their multiple locations into a list."""
    search_query = request.args.get('search', '').strip()
    
    base_query = """
        SELECT c.company_id, c.name, c.industry, c.contact_email, 
               GROUP_CONCAT(cl.location ORDER BY cl.location_id SEPARATOR ', ') AS locations_list 
        FROM company c 
        LEFT JOIN company_location cl ON c.company_id = cl.company_id
    """
    
    if search_query:
        query = base_query + " WHERE c.name LIKE %s OR c.industry LIKE %s GROUP BY c.company_id ORDER BY c.company_id DESC"
        companies = execute_query(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        query = base_query + " GROUP BY c.company_id ORDER BY c.company_id DESC"
        companies = execute_query(query)
        
    return render_template('company_details.html', companies=companies, search_query=search_query)


@app.route('/companies/create', methods=['POST'])
@login_required
def create_company():
    """Handles company creation and dynamically inserts locations in a transaction."""
    name = request.form.get('name', '').strip()
    industry = request.form.get('industry', '').strip()
    contact_email = request.form.get('contact_email', '').strip()
    locations_str = request.form.get('locations', '').strip()
    
    try:
        # Insert company
        res = execute_dml(
            "INSERT INTO company (name, industry, contact_email) VALUES (%s, %s, %s)",
            (name, industry, contact_email)
        )
        company_id = res['lastrowid']
        
        # Insert multiple locations
        if locations_str:
            locations = [l.strip() for l in locations_str.split(',') if l.strip()]
            for loc in locations:
                execute_dml("INSERT INTO company_location (company_id, location) VALUES (%s, %s)", (company_id, loc))
                
        flash(f"Company '{name}' added successfully with locations!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_companies'))


@app.route('/companies/edit', methods=['POST'])
@login_required
def edit_company():
    """Updates company information and replaces locations inside a single transaction."""
    company_id = request.form.get('company_id')
    name = request.form.get('name', '').strip()
    industry = request.form.get('industry', '').strip()
    contact_email = request.form.get('contact_email', '').strip()
    locations_str = request.form.get('locations', '').strip()
    
    try:
        # Update details
        execute_dml(
            "UPDATE company SET name=%s, industry=%s, contact_email=%s WHERE company_id=%s",
            (name, industry, contact_email, company_id)
        )
        
        # Clear existing locations
        execute_dml("DELETE FROM company_location WHERE company_id=%s", (company_id,))
        
        # Insert new locations
        if locations_str:
            locations = [l.strip() for l in locations_str.split(',') if l.strip()]
            for loc in locations:
                execute_dml("INSERT INTO company_location (company_id, location) VALUES (%s, %s)", (company_id, loc))
                
        flash(f"Company details and locations updated successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_companies'))


@app.route('/companies/delete/<int:company_id>')
@login_required
def delete_company(company_id):
    """Deletes a company record, automatically cascading locations and roles."""
    try:
        execute_dml("DELETE FROM company WHERE company_id = %s", (company_id,))
        flash("Company and all associated roles deleted successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Deletion failed: {err.msg}", "danger")
    return redirect(url_for('list_companies'))


# =========================================================
# JOB ROLES CRUD
# =========================================================
@app.route('/roles')
@login_required
def list_roles():
    """Lists job roles and companies for dropdown select menus."""
    search_query = request.args.get('search', '').strip()
    
    base_query = """
        SELECT r.role_id, r.company_id, r.title, r.package, r.role_type, r.eligibility_cgpa, 
               r.deadline, r.description, r.is_active, c.name AS company_name 
        FROM job_role r 
        JOIN company c ON r.company_id = c.company_id
    """
    
    if search_query:
        query = base_query + " WHERE c.name LIKE %s OR r.title LIKE %s ORDER BY r.role_id DESC"
        roles = execute_query(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        query = base_query + " ORDER BY r.role_id DESC"
        roles = execute_query(query)
        
    companies = execute_query("SELECT company_id, name FROM company ORDER BY name ASC")
    return render_template('job_roles.html', roles=roles, companies=companies, search_query=search_query)


@app.route('/roles/create', methods=['POST'])
@login_required
def create_role():
    """Creates a job role."""
    company_id = request.form.get('company_id')
    title = request.form.get('title', '').strip()
    package = request.form.get('package', '0.0')
    role_type = request.form.get('role_type', 'Internship')
    eligibility_cgpa = request.form.get('eligibility_cgpa', '0.0')
    deadline = request.form.get('deadline')
    description = request.form.get('description', '').strip()
    is_active = 1 if request.form.get('is_active') == '1' else 0
    
    try:
        execute_dml(
            """
            INSERT INTO job_role (company_id, title, package, role_type, eligibility_cgpa, deadline, description, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (company_id, title, package, role_type, eligibility_cgpa, deadline, description, is_active)
        )
        flash(f"Job role '{title}' posted successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_roles'))


@app.route('/roles/edit', methods=['POST'])
@login_required
def edit_role():
    """Updates a job role details."""
    role_id = request.form.get('role_id')
    company_id = request.form.get('company_id')
    title = request.form.get('title', '').strip()
    package = request.form.get('package', '0.0')
    role_type = request.form.get('role_type', 'Internship')
    eligibility_cgpa = request.form.get('eligibility_cgpa', '0.0')
    deadline = request.form.get('deadline')
    description = request.form.get('description', '').strip()
    is_active = 1 if request.form.get('is_active') == '1' else 0
    
    try:
        execute_dml(
            """
            UPDATE job_role 
            SET company_id=%s, title=%s, package=%s, role_type=%s, eligibility_cgpa=%s, deadline=%s, description=%s, is_active=%s
            WHERE role_id=%s
            """,
            (company_id, title, package, role_type, eligibility_cgpa, deadline, description, is_active, role_id)
        )
        flash(f"Job role details updated successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_roles'))


@app.route('/roles/delete/<int:role_id>')
@login_required
def delete_role(role_id):
    """Deletes a job role record."""
    try:
        execute_dml("DELETE FROM job_role WHERE role_id = %s", (role_id,))
        flash("Job role deleted successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Deletion failed: {err.msg}", "danger")
    return redirect(url_for('list_roles'))


# =========================================================
# JOB APPLICATIONS CRUD & TRIGGER / PROCEDURE integration
# =========================================================
@app.route('/applications')
@login_required
def list_applications():
    """Lists applications, fetches students and roles for dropdowns."""
    search_query = request.args.get('search', '').strip()
    
    base_query = """
        SELECT a.application_id, a.student_id, a.role_id, a.application_date, a.current_status, 
               s.name AS student_name, s.cgpa AS student_cgpa, s.resume_url, r.title AS role_title, 
               c.name AS company_name 
        FROM job_application a 
        JOIN student s ON a.student_id = s.student_id 
        JOIN job_role r ON a.role_id = r.role_id 
        JOIN company c ON r.company_id = c.company_id
    """
    
    if search_query:
        query = base_query + " WHERE s.name LIKE %s OR c.name LIKE %s ORDER BY a.application_id DESC"
        applications = execute_query(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        query = base_query + " ORDER BY a.application_id DESC"
        applications = execute_query(query)
        
    # Query datasets for creation selectors
    students = execute_query("SELECT student_id, name, branch, cgpa, resume_url FROM student ORDER BY name ASC")
    roles = execute_query("SELECT r.role_id, r.title, r.eligibility_cgpa, r.deadline, r.is_active, c.name AS company_name FROM job_role r JOIN company c ON r.company_id = c.company_id ORDER BY c.name ASC")
    
    return render_template('applications.html', applications=applications, students=students, roles=roles, search_query=search_query)


@app.route('/applications/create', methods=['POST'])
@login_required
def create_application():
    """Calls `apply_for_role` procedure, trapping SQLSTATE '45000' trigger validation exceptions."""
    student_id = request.form.get('student_id')
    role_id = request.form.get('role_id')
    
    try:
        # Executes DB stored procedure apply_for_role(student_id, role_id)
        call_procedure("apply_for_role", [student_id, role_id])
        flash("Application submitted successfully! Database verified eligibility constraints.", "success")
    except mysql.connector.Error as err:
        # Check if error was raised by trigger validation (SIGNAL SQLSTATE '45000')
        if err.sqlstate == '45000':
            flash(f"Eligibility Constraint Violated: {err.msg}", "danger")
        else:
            flash(f"Database Error: {err.msg}", "danger")
            
    return redirect(url_for('list_applications'))


@app.route('/applications/edit', methods=['POST'])
@login_required
def edit_application():
    """Updates application status manually."""
    application_id = request.form.get('application_id')
    current_status = request.form.get('current_status', 'Applied')
    
    try:
        execute_dml(
            "UPDATE job_application SET current_status = %s WHERE application_id = %s",
            (current_status, application_id)
        )
        # If set to selected, we call generate_offer procedure just in case
        if current_status == 'Selected':
            call_procedure("generate_offer", [application_id])
            flash("Application status updated to 'Selected'. Pending offer record automatically generated!", "success")
        else:
            flash("Application status updated successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_applications'))


@app.route('/applications/delete/<int:application_id>')
@login_required
def delete_application(application_id):
    """Deletes an application record."""
    try:
        execute_dml("DELETE FROM job_application WHERE application_id = %s", (application_id,))
        flash("Job application deleted successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Deletion failed: {err.msg}", "danger")
    return redirect(url_for('list_applications'))


# =========================================================
# OFFERS CRUD & PROCEDURE / TRIGGER integration
# =========================================================
@app.route('/offers')
@login_required
def list_offers():
    """Lists offers, and lists selected applications for manual offer generation."""
    search_query = request.args.get('search', '').strip()
    
    base_query = """
        SELECT o.offer_id, o.application_id, o.offer_date, o.offer_status, o.accepted_at, 
               s.name AS student_name, r.title AS role_title, r.role_type, r.package, c.name AS company_name 
        FROM offer_record o 
        JOIN job_application a ON o.application_id = a.application_id 
        JOIN student s ON a.student_id = s.student_id 
        JOIN job_role r ON a.role_id = r.role_id 
        JOIN company c ON r.company_id = c.company_id
    """
    
    if search_query:
        query = base_query + " WHERE s.name LIKE %s OR c.name LIKE %s ORDER BY o.offer_id DESC"
        offers = execute_query(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        query = base_query + " ORDER BY o.offer_id DESC"
        offers = execute_query(query)
        
    # Get Selected applications that don't have an offer yet for manual generation
    applications = execute_query(
        """
        SELECT a.application_id, s.name AS student_name, c.name AS company_name, r.title AS role_title, a.current_status 
        FROM job_application a 
        JOIN student s ON a.student_id = s.student_id 
        JOIN job_role r ON a.role_id = r.role_id 
        JOIN company c ON r.company_id = c.company_id 
        LEFT JOIN offer_record o ON a.application_id = o.application_id 
        WHERE a.current_status = 'Selected' AND o.offer_id IS NULL
        """
    )
    
    return render_template('offers.html', offers=offers, applications=applications, search_query=search_query)


@app.route('/offers/create', methods=['POST'])
@login_required
def create_offer():
    """Calls `generate_offer` procedure."""
    application_id = request.form.get('application_id')
    
    try:
        call_procedure("generate_offer", [application_id])
        flash("Offer successfully generated in 'Pending' status!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_offers'))


@app.route('/offers/edit', methods=['POST'])
@login_required
def edit_offer():
    """Processes offers status using accept_offer/reject_offer procedures, capturing double-offer checks."""
    offer_id = request.form.get('offer_id')
    offer_status = request.form.get('offer_status')
    
    try:
        if offer_status == 'Accepted':
            # Call procedure accept_offer(offer_id) which updates status and timestamps accepted_at
            # This triggers trg_offer_acceptance BEFORE UPDATE
            call_procedure("accept_offer", [offer_id])
            flash("Offer successfully accepted!", "success")
        elif offer_status == 'Rejected':
            # Call procedure reject_offer(offer_id)
            call_procedure("reject_offer", [offer_id])
            flash("Offer declined and status marked as Rejected.", "warning")
        else:
            # Revert to pending
            execute_dml("UPDATE offer_record SET offer_status = 'Pending', accepted_at = NULL WHERE offer_id = %s", (offer_id,))
            flash("Offer reverted to 'Pending'.", "info")
            
    except mysql.connector.Error as err:
        if err.sqlstate == '45000':
            # Intercept 'Student already accepted a full-time offer' trigger check
            flash(f"Offer Blocked: {err.msg}", "danger")
        else:
            flash(f"Database Error: {err.msg}", "danger")
            
    return redirect(url_for('list_offers'))


@app.route('/offers/delete/<int:offer_id>')
@login_required
def delete_offer(offer_id):
    """Deletes an offer record."""
    try:
        execute_dml("DELETE FROM offer_record WHERE offer_id = %s", (offer_id,))
        flash("Offer record deleted successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Deletion failed: {err.msg}", "danger")
    return redirect(url_for('list_offers'))


# =========================================================
# SELECTION STAGES CRUD
# =========================================================
@app.route('/stages')
@login_required
def list_stages():
    """Lists selection stages and roles for dropdown selectors."""
    search_query = request.args.get('search', '').strip()
    
    base_query = """
        SELECT s.stage_id, s.role_id, s.stage_number, s.stage_type, 
               r.title AS role_title, c.name AS company_name 
        FROM selection_stage s 
        JOIN job_role r ON s.role_id = r.role_id 
        JOIN company c ON r.company_id = c.company_id
    """
    
    if search_query:
        query = base_query + " WHERE r.title LIKE %s OR s.stage_type LIKE %s ORDER BY s.role_id DESC, s.stage_number ASC"
        stages = execute_query(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        query = base_query + " ORDER BY s.role_id DESC, s.stage_number ASC"
        stages = execute_query(query)
        
    roles = execute_query("SELECT r.role_id, r.title, r.deadline, c.name AS company_name FROM job_role r JOIN company c ON r.company_id = c.company_id ORDER BY c.name ASC")
    return render_template('selection_stages.html', stages=stages, roles=roles, search_query=search_query)


@app.route('/stages/create', methods=['POST'])
@login_required
def create_stage():
    """Creates selection stage."""
    role_id = request.form.get('role_id')
    stage_number = request.form.get('stage_number')
    stage_type = request.form.get('stage_type', '').strip()
    
    try:
        execute_dml(
            "INSERT INTO selection_stage (role_id, stage_number, stage_type) VALUES (%s, %s, %s)",
            (role_id, stage_number, stage_type)
        )
        flash(f"Stage {stage_number} ({stage_type}) added successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_stages'))


@app.route('/stages/edit', methods=['POST'])
@login_required
def edit_stage():
    """Updates selection stage details."""
    stage_id = request.form.get('stage_id')
    role_id = request.form.get('role_id')
    stage_number = request.form.get('stage_number')
    stage_type = request.form.get('stage_type', '').strip()
    
    try:
        execute_dml(
            "UPDATE selection_stage SET role_id=%s, stage_number=%s, stage_type=%s WHERE stage_id=%s",
            (role_id, stage_number, stage_type, stage_id)
        )
        flash(f"Stage details updated successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_stages'))


@app.route('/stages/delete/<int:stage_id>')
@login_required
def delete_stage(stage_id):
    """Deletes stage record."""
    try:
        execute_dml("DELETE FROM selection_stage WHERE stage_id = %s", (stage_id,))
        flash("Stage deleted successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Deletion failed: {err.msg}", "danger")
    return redirect(url_for('list_stages'))


# =========================================================
# STAGE RESULTS CRUD & STAGE RESULT TRIGGER AUTOMATION
# =========================================================
@app.route('/results')
@login_required
def list_results():
    """Lists stage results, applications and stages for selector dropdowns."""
    search_query = request.args.get('search', '').strip()
    
    base_query = """
        SELECT sr.result_id, sr.application_id, sr.stage_id, sr.result_status, 
               s.name AS student_name, r.title AS role_title, c.name AS company_name, 
               ss.stage_number, ss.stage_type 
        FROM stage_result sr 
        JOIN job_application a ON sr.application_id = a.application_id 
        JOIN student s ON a.student_id = s.student_id 
        JOIN selection_stage ss ON sr.stage_id = ss.stage_id 
        JOIN job_role r ON ss.role_id = r.role_id 
        JOIN company c ON r.company_id = c.company_id
    """
    
    if search_query:
        query = base_query + " WHERE s.name LIKE %s OR ss.stage_type LIKE %s ORDER BY sr.result_id DESC"
        results = execute_query(query, (f"%{search_query}%", f"%{search_query}%"))
    else:
        query = base_query + " ORDER BY sr.result_id DESC"
        results = execute_query(query)
        
    # Query datasets for selectors
    applications = execute_query(
        """
        SELECT a.application_id, a.role_id, s.name AS student_name, c.name AS company_name, r.title AS role_title, a.current_status 
        FROM job_application a 
        JOIN student s ON a.student_id = s.student_id 
        JOIN job_role r ON a.role_id = r.role_id 
        JOIN company c ON r.company_id = c.company_id 
        WHERE a.current_status IN ('Applied', 'In Process')
        """
    )
    
    stages = execute_query(
        """
        SELECT s.stage_id, s.role_id, s.stage_number, s.stage_type, r.title AS role_title, c.name AS company_name 
        FROM selection_stage s 
        JOIN job_role r ON s.role_id = r.role_id 
        JOIN company c ON r.company_id = c.company_id 
        ORDER BY c.name ASC, s.stage_number ASC
        """
    )
    
    return render_template('stage_results.html', results=results, applications=applications, stages=stages, search_query=search_query)


@app.route('/results/create', methods=['POST'])
@login_required
def create_result():
    """Logs a student stage result, firing database automation trigger `trg_stage_result`."""
    application_id = request.form.get('application_id')
    stage_id = request.form.get('stage_id')
    result_status = request.form.get('result_status', 'Pass')
    
    try:
        # Logs result, which executes trg_stage_result automatically inside the DB
        execute_dml(
            "INSERT INTO stage_result (application_id, stage_id, result_status) VALUES (%s, %s, %s)",
            (application_id, stage_id, result_status)
        )
        
        # Pull application status to see if trigger auto-updated the application status
        app_status_q = execute_query(
            "SELECT current_status FROM job_application WHERE application_id = %s",
            (application_id,), fetch="one"
        )
        status = app_status_q['current_status'] if app_status_q else 'Applied'
        
        if status == 'Selected':
            flash("Stage result saved! All stages passed! Application status auto-updated to 'Selected' and pending Offer Record created.", "success")
        elif status == 'Rejected':
            flash("Stage result saved! Stage failed. Application status automatically updated to 'Rejected'.", "warning")
        else:
            flash(f"Stage result saved successfully. Application status set to '{status}'.", "success")
            
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_results'))


@app.route('/results/edit', methods=['POST'])
@login_required
def edit_result():
    """Updates logged stage result."""
    result_id = request.form.get('result_id')
    result_status = request.form.get('result_status', 'Pass')
    
    try:
        execute_dml(
            "UPDATE stage_result SET result_status = %s WHERE result_id = %s",
            (result_status, result_id)
        )
        flash("Stage result updated successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err.msg}", "danger")
        
    return redirect(url_for('list_results'))


@app.route('/results/delete/<int:result_id>')
@login_required
def delete_result(result_id):
    """Deletes stage result record."""
    try:
        execute_dml("DELETE FROM stage_result WHERE result_id = %s", (result_id,))
        flash("Stage result deleted successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Deletion failed: {err.msg}", "danger")
    return redirect(url_for('list_results'))


if __name__ == '__main__':
    app.run(debug=True)