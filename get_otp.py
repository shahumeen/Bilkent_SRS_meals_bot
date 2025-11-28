import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def get_otp_from_webmail(email, email_password, wait_time=60):
    """
    Login to Bilkent webmail and retrieve OTP from the first email, then delete the email.

    Args:
        email (str): Bilkent email address
        email_password (str): Email password
        wait_time (int): Maximum time to wait for email (default: 60 seconds)

    Returns:
        str: OTP code if found, None if failed
    """
    driver = None
    try:
        # Initialize Chrome driver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Additional options for better stability
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(options=options)

        # Remove webdriver property
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        wait = WebDriverWait(driver, 30)  # Increased timeout

        print("Navigating to Bilkent webmail...")
        driver.get("https://webmail.bilkent.edu.tr/")

        # Wait for login form to load
        print("Waiting for login form...")
        # time.sleep(0.5)  # Give page time to fully load

        email_field = wait.until(EC.element_to_be_clickable((By.ID, "rcmloginuser")))
        password_field = wait.until(EC.element_to_be_clickable((By.ID, "rcmloginpwd")))

        # Fill in credentials with delays
        print("Logging in with email")
        email_field.clear()
        # time.sleep(0.5)
        email_field.send_keys(email)
        # time.sleep(0.5)
        password_field.clear()
        # time.sleep(0.5)
        password_field.send_keys(email_password)
        # time.sleep(0.5)

        # Submit login form
        login_button = wait.until(EC.element_to_be_clickable((By.ID, "rcmloginsubmit")))
        login_button.click()

        # Wait for successful login - look for inbox with longer timeout
        print("Waiting for successful login...")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "mailboxlist"))
        )

        # Wait for new email to arrive with retry mechanism
        print(f"Waiting up to {wait_time} seconds for OTP email...")
        end_time = time.time() + wait_time
        otp = None

        while time.time() < end_time and not otp:
            try:
                # Refresh the inbox
                refresh_button = driver.find_element(By.ID, "rcmbtn112")
                refresh_button.click()

                # Wait a moment for refresh to complete
                time.sleep(0.13)

                # Look for the email list table
                try:
                    # Wait for messagelist to be populated
                    wait_short = WebDriverWait(driver, 5)
                    wait_short.until(
                        lambda d: d.find_elements(
                            By.CSS_SELECTOR, "#messagelist tbody tr"
                        )
                    )

                    # Try to find emails in the messagelist
                    messagelist = driver.find_element(By.ID, "messagelist")

                    # Look for email rows - try multiple selectors
                    email_rows = (
                        messagelist.find_elements(By.CSS_SELECTOR, "tbody tr")
                        or messagelist.find_elements(By.CSS_SELECTOR, "tr.message")
                        or messagelist.find_elements(By.CSS_SELECTOR, "tr[id]")
                    )

                    if email_rows:
                        print(
                            f"Found {len(email_rows)} email(s), checking the first one..."
                        )

                        # Get the first email row that's not a header
                        for email_row in email_rows:
                            # Skip header rows or empty rows
                            if email_row.get_attribute(
                                "class"
                            ) and "thead" in email_row.get_attribute("class"):
                                continue
                            if not email_row.text.strip():
                                continue

                            # Check if this email is from STARS (look for sender info in the row)
                            row_text = email_row.text.lower()
                            if any(
                                keyword in row_text
                                for keyword in [
                                    "starsmsg",
                                    "bilkent",
                                    "verification",
                                    "secure login",
                                ]
                            ):
                                print(
                                    f"Found STARS email, clicking: {email_row.text[:100]}..."
                                )
                                email_row.click()
                                break
                            else:
                                print(
                                    f"Skipping non-STARS email: {email_row.text[:50]}..."
                                )
                        else:
                            # If no STARS email found, click the first email as fallback
                            if email_rows:
                                print(
                                    "No STARS email found, clicking first email as fallback..."
                                )
                                email_rows[0].click()

                        # Wait for email content to load
                        time.sleep(0.091)

                        # Look for the email content iframe or direct content
                        email_content = ""
                        try:
                            # Try to switch to content frame
                            iframe = wait.until(
                                EC.presence_of_element_located(
                                    (By.ID, "messagecontframe")
                                )
                            )
                            driver.switch_to.frame(iframe)
                            email_content = driver.page_source
                            print("Found email content in iframe")
                        except:
                            # If no iframe, get content from main page
                            driver.switch_to.default_content()
                            email_content = driver.page_source
                            print("Using main page content")

                        print("Searching for OTP in email content...")

                        # Extract OTP using multiple patterns
                        otp_patterns = [
                            r"Verification Code:\s*(\d{5,6})",
                            r"Code:\s*(\d{5,6})",
                            r"OTP:\s*(\d{5,6})",
                            r"(\d{5,6})\s*for your.*verification",
                            r"verification.*code[:\s]+(\d{5,6})",
                            r"\b(\d{5,6})\b",  # Any 5-6 digit number as fallback
                        ]

                        for pattern in otp_patterns:
                            match = re.search(pattern, email_content, re.IGNORECASE)
                            if match:
                                otp = match.group(1)
                                print(f"✓ Found OTP using pattern '{pattern}': {otp}")
                                break

                        if otp:
                            # Switch back to default content before deleting
                            driver.switch_to.default_content()

                            # Delete the email
                            print("Deleting the email...")
                            try:
                                # Look for delete button with multiple selectors
                                delete_selectors = [
                                    "a.delete[title*='trash']",
                                    "#rcmbtn124",
                                    "a[onclick*='delete']",
                                    ".delete",
                                ]

                                delete_button = None
                                for selector in delete_selectors:
                                    try:
                                        delete_button = driver.find_element(
                                            By.CSS_SELECTOR, selector
                                        )
                                        if delete_button.is_displayed():
                                            break
                                    except:
                                        continue

                                if delete_button:
                                    delete_button.click()
                                    time.sleep(0.13)
                                    print("✓ Email deleted successfully")
                                else:
                                    print("Warning: Could not find delete button")

                            except Exception as e:
                                print(f"Warning: Could not delete email: {e}")

                            break
                        else:
                            print(
                                "No OTP found in this email, waiting for new email..."
                            )
                            driver.switch_to.default_content()

                    else:
                        print("No emails found yet, waiting...")

                except Exception as e:
                    print(f"Error checking emails: {e}")

                # Wait before next check if no OTP found yet
                if not otp:
                    time.sleep(5)

            except Exception as e:
                print(f"Error during email check: {e}")
                time.sleep(5)

        if not otp:
            print("Timeout waiting for OTP email")

        return otp

    except Exception as e:
        print(f"Error in get_otp_from_webmail: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        # Close the browser
        if driver:
            driver.quit()


if __name__ == "__main__":
    # Test configuration
    EMAIL = "name.surname@ug.bilkent.edu.tr"
    EMAIL_PASSWORD = "emailpass"

    print("=" * 60)
    print("TESTING WEBMAIL OTP RETRIEVAL")
    print("=" * 60)

    otp = get_otp_from_webmail(EMAIL, EMAIL_PASSWORD, wait_time=60)

    print("\n" + "=" * 60)
    if otp:
        print(f"SUCCESS! Retrieved OTP: {otp}")
    else:
        print("FAILED to retrieve OTP from email")
    print("=" * 60)
