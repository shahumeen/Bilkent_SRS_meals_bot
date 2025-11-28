import time
import re
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from get_otp import get_otp_from_webmail


class OTPRetrievalError(Exception):
    """Raised when OTP cannot be retrieved from email."""

    pass


class LoginCredentialsError(Exception):
    """Raised when login credentials are incorrect."""

    pass


def save_cookies(driver, filepath):
    """Save cookies to file"""
    try:
        with open(filepath, "w") as f:
            json.dump(driver.get_cookies(), f)
    except Exception as e:
        pass


def load_cookies(driver, filepath):
    """Load cookies from file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                cookies = json.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
            return True
    except Exception as e:
        pass
    return False


import asyncio


async def get_remaining_meals(
    bilkent_id, stars_password, email, email_password, status_callback=None
):
    """
    Login to STARS system and retrieve remaining meal count.

    Args:
        bilkent_id (str): Bilkent ID number
        stars_password (str): STARS password
        email (str): Bilkent email address for OTP
        email_password (str): Email password
        status_callback (callable): Optional async function to call with status updates

    Returns:
        int: Number of remaining meals, None if failed
    """

    async def update_status(message: str):
        """Helper to update status if callback is provided"""
        if status_callback:
            await status_callback(message)

    driver = None
    try:
        # Initialize Chrome driver with anti-detection settings
        options = webdriver.ChromeOptions()

        # Headless mode
        options.add_argument("--headless=new")

        # Basic stealth settings
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Anti-detection settings
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins-discovery")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")

        # User agent to appear as regular browser
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Additional stealth settings
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-ipc-flooding-protection")

        driver = webdriver.Chrome(options=options)

        # Execute script to remove webdriver property
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Set additional properties to mimic real browser
        driver.execute_script(
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """
        )

        wait = WebDriverWait(driver, 15)

        # Navigate to STARS login page
        print("Navigating to STARS login page...")
        await update_status("🔐 Logging in to SRS...")
        driver.get("https://stars.bilkent.edu.tr/srs/")

        # Add some human-like delay
        await asyncio.sleep(0.12)  # Fill in Bilkent ID and password
        print("Entering credentials...")
        bilkent_id_field = wait.until(
            EC.presence_of_element_located((By.ID, "LoginForm_username"))
        )
        password_field = driver.find_element(By.ID, "LoginForm_password")

        # Human-like typing with delays
        bilkent_id_field.clear()
        await asyncio.sleep(0.21)
        for char in bilkent_id:
            bilkent_id_field.send_keys(char)
            # await asyncio.sleep(0.17)

        # await asyncio.sleep(0.31)
        password_field.clear()
        for char in stars_password:
            password_field.send_keys(char)
            # await asyncio.sleep(0.21)

        # Submit login form
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()

        # Check for login error message
        try:
            # Wait briefly to see if error message appears
            await asyncio.sleep(0.23)
            page_source = driver.page_source
            
            # Check for incorrect credentials message
            if "The password or Bilkent ID number entered is incorrect." in page_source:
                print("❌ Login failed: Incorrect Bilkent ID or password")
                await update_status("❌ Login failed: Incorrect Bilkent ID or password")
                raise LoginCredentialsError("The password or Bilkent ID number entered is incorrect.")
                
        except LoginCredentialsError:
            # Re-raise the login error
            raise
        except Exception as e:
            # Continue if we can't check for error (maybe page is loading)
            pass

        # Wait for OTP page to load
        print("Waiting for OTP verification page...")

        # Check if we're on the email verification page
        try:
            otp_field = wait.until(
                EC.presence_of_element_located((By.ID, "EmailVerifyForm_verifyCode"))
            )
            print("OTP page loaded successfully")
        except:
            print(
                "❌ Failed to load OTP page. Make sure to type the passwords correctly."
            )
            return None

        # Get OTP from email
        print("\nFetching OTP from email...")
        await update_status("📧 Getting OTP code...")
        otp = get_otp_from_webmail(email, email_password, wait_time=60)

        if not otp:
            print("Failed to retrieve OTP from email")
            # Inform user without exposing technical details
            await update_status("Failed to retrieve OTP from email")
            # Raise a specific error to let caller decide messaging
            raise OTPRetrievalError("Failed to retrieve OTP from email")

        print(f"\nOTP received: {otp}")
        await update_status(f"🔑 OTP received: {otp}")

        # Enter OTP in the verification form
        print(f"Entering OTP...")
        otp_field.clear()
        await asyncio.sleep(0.19)

        # Human-like typing for OTP
        for char in otp:
            otp_field.send_keys(char)
            await asyncio.sleep(0.23)

        await asyncio.sleep(0.12)

        # Submit OTP form
        verify_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        verify_button.click()

        # Wait for successful login with better error handling
        print("Verifying OTP...")
        try:
            # Wait for redirect after successful OTP verification
            wait.until(
                lambda driver: "login" not in driver.current_url
                or "meal" in driver.current_url
            )
            print("✓ OTP verification successful")
            await update_status("✅ SRS login successful\n⏳ Fetching meal data...")

        except TimeoutException:
            print("Timeout during OTP verification")
            return None

        # Add delay before navigating to meals page
        await asyncio.sleep(0.21)

        # Navigate to meals page
        print("Navigating to meals page...")
        driver.get("https://stars.bilkent.edu.tr/srs-v2/meal/order")

        # Wait for page to load
        await asyncio.sleep(0.34)

        # Check if we got redirected back to login (authentication failed)
        final_url = driver.current_url
        if "login" in final_url.lower() or "auth" in final_url.lower():
            print("Authentication failed - redirected back to login")
            return None

        # Wait for page content to load properly
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait for meal page elements to load
        max_wait_attempts = 3
        page_source = None

        for attempt in range(max_wait_attempts):
            try:
                await asyncio.sleep(0.34)

                # Try to find meal page elements
                try:
                    wait.until(
                        EC.any_of(
                            EC.presence_of_element_located((By.CLASS_NAME, "badge")),
                            EC.presence_of_element_located(
                                (By.PARTIAL_LINK_TEXT, "meal")
                            ),
                            EC.text_to_be_present_in_element(
                                (By.TAG_NAME, "body"), "meal"
                            ),
                            EC.text_to_be_present_in_element(
                                (By.TAG_NAME, "body"), "remaining"
                            ),
                        ),
                        timeout=5,
                    )
                except:
                    pass

                page_source = driver.page_source

                # Check if page has meaningful content
                if len(page_source) > 1000 and (
                    "meal" in page_source.lower() or "badge" in page_source.lower()
                ):
                    break
                elif attempt < max_wait_attempts - 1:
                    driver.refresh()
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            except Exception as e:
                if attempt < max_wait_attempts - 1:
                    driver.refresh()
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        if not page_source:
            page_source = driver.page_source

        # Try to find the remaining meals count with multiple patterns
        meals_patterns = [
            r'Remaining number of meals:\s*<span class="badge">(\d+)</span>',
            r"remaining meals?:\s*(\d+)",
            r"meals? remaining:\s*(\d+)",
            r'<span class="badge">(\d+)</span>',
            r"(\d+)\s*meals? left",
            r"balance.*?(\d+)",
        ]

        remaining_meals = None
        for pattern in meals_patterns:
            meals_match = re.search(pattern, page_source, re.IGNORECASE)
            if meals_match:
                remaining_meals = int(meals_match.group(1))
                break

        if remaining_meals:
            return remaining_meals
        else:
            print("Could not find remaining meals count on page")
            return None

    except TimeoutException:
        print("Timeout waiting for page elements to load")
        return None
    except Exception as e:
        print(f"Error during STARS login: {e}")
        import traceback

        traceback.print_exc()
        return None
    finally:
        # Close the browser
        if driver:
            driver.quit()


if __name__ == "__main__":
    # Configuration
    BILKENT_ID = "12345678"
    STARS_PASSWORD = "srspass"
    EMAIL = "name.surname@ug.bilkent.edu.tr"
    EMAIL_PASSWORD = "emailpass"

    print("=" * 60)
    print("BILKENT STARS MEAL CHECKER")
    print("=" * 60)

    remaining_meals = asyncio.run(
        get_remaining_meals(
            bilkent_id=BILKENT_ID,
            stars_password=STARS_PASSWORD,
            email=EMAIL,
            email_password=EMAIL_PASSWORD,
        )
    )

    print("\n" + "=" * 60)
    if remaining_meals is not None:
        print(f"SUCCESS! You have {remaining_meals} meals remaining.")
    else:
        print("FAILED to retrieve remaining meals count.")
    print("=" * 60)
