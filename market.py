def update_market_prices(cursor):
    # Prix +5% si personne ne farm, -5% si sur-peuplé
    cursor.execute("UPDATE Tokens SET current_value = current_value * 1.05 WHERE total_farmers = 0")
    cursor.execute("UPDATE Tokens SET current_value = current_value * 0.95 WHERE total_farmers > 1")
    # Sécurité prix mini
    cursor.execute("UPDATE Tokens SET current_value = 10 WHERE current_value < 10")
