"""Hand-written natural-language questions with hand-verified ground-truth
SQL, executed against data/chinook.db during authoring to confirm each
query actually runs and returns a sensible result (see docs/evaluation-report.md
for the verification methodology).
"""

QUESTIONS = [
    # --- single-table lookups (8) ---
    {
        "id": "S1",
        "category": "single_table",
        "question": "How many artists are in the database?",
        "sql": "SELECT COUNT(*) FROM artists;",
    },
    {
        "id": "S2",
        "category": "single_table",
        "question": "How many tracks are there in total?",
        "sql": "SELECT COUNT(*) FROM tracks;",
    },
    {
        "id": "S3",
        "category": "single_table",
        "question": "What is the email address of the customer with CustomerId 10?",
        "sql": "SELECT Email FROM customers WHERE CustomerId = 10;",
    },
    {
        "id": "S4",
        "category": "single_table",
        "question": "List all genre names in the database, alphabetically.",
        "sql": "SELECT Name FROM genres ORDER BY Name;",
    },
    {
        "id": "S5",
        "category": "single_table",
        "question": "How many employees work at the company?",
        "sql": "SELECT COUNT(*) FROM employees;",
    },
    {
        "id": "S6",
        "category": "single_table",
        "question": "What is the title of the album with AlbumId 1?",
        "sql": "SELECT Title FROM albums WHERE AlbumId = 1;",
    },
    {
        "id": "S7",
        "category": "single_table",
        "question": "How many playlists are there?",
        "sql": "SELECT COUNT(*) FROM playlists;",
    },
    {
        "id": "S8",
        "category": "single_table",
        "question": "What are the names of all the available media types?",
        "sql": "SELECT Name FROM media_types ORDER BY MediaTypeId;",
    },
    # --- multi-table joins, no aggregation (12) ---
    {
        "id": "J1",
        "category": "join",
        "question": "What genre is the track \"Balls to the Wall\"?",
        "sql": "SELECT g.Name FROM tracks t JOIN genres g ON t.GenreId = g.GenreId WHERE t.Name = 'Balls to the Wall';",
    },
    {
        "id": "J2",
        "category": "join",
        "question": "Which artist made the album \"Jagged Little Pill\"?",
        "sql": "SELECT ar.Name FROM albums a JOIN artists ar ON a.ArtistId = ar.ArtistId WHERE a.Title = 'Jagged Little Pill';",
    },
    {
        "id": "J3",
        "category": "join",
        "question": "Who is the manager of employee Jane Peacock?",
        "sql": "SELECT m.FirstName, m.LastName FROM employees e JOIN employees m ON e.ReportsTo = m.EmployeeId WHERE e.FirstName = 'Jane' AND e.LastName = 'Peacock';",
    },
    {
        "id": "J4",
        "category": "join",
        "question": "Who does employee Robert King report to?",
        "sql": "SELECT m.FirstName, m.LastName FROM employees e JOIN employees m ON e.ReportsTo = m.EmployeeId WHERE e.FirstName = 'Robert' AND e.LastName = 'King';",
    },
    {
        "id": "J5",
        "category": "join",
        "question": "What country is the customer who placed invoice 404 from?",
        "sql": "SELECT c.Country FROM invoices i JOIN customers c ON i.CustomerId = c.CustomerId WHERE i.InvoiceId = 404;",
    },
    {
        "id": "J6",
        "category": "join",
        "question": "List the names of all tracks on the album \"Jagged Little Pill\".",
        "sql": "SELECT t.Name FROM tracks t JOIN albums a ON t.AlbumId = a.AlbumId WHERE a.Title = 'Jagged Little Pill';",
    },
    {
        "id": "J7",
        "category": "join",
        "question": "What is the longest track, by duration, on the album \"Jagged Little Pill\"?",
        "sql": "SELECT t.Name FROM tracks t JOIN albums a ON t.AlbumId = a.AlbumId WHERE a.Title = 'Jagged Little Pill' ORDER BY t.Milliseconds DESC LIMIT 1;",
    },
    {
        "id": "J8",
        "category": "join",
        "question": "What is the full name and email of the customer who placed invoice 404?",
        "sql": "SELECT c.FirstName, c.LastName, c.Email FROM invoices i JOIN customers c ON i.CustomerId = c.CustomerId WHERE i.InvoiceId = 404;",
    },
    {
        "id": "J9",
        "category": "join",
        "question": "What is the title of the album that contains the track \"Balls to the Wall\"?",
        "sql": "SELECT a.Title FROM tracks t JOIN albums a ON t.AlbumId = a.AlbumId WHERE t.Name = 'Balls to the Wall';",
    },
    {
        "id": "J10",
        "category": "join",
        "question": "What media type is the track \"Balls to the Wall\" available as?",
        "sql": "SELECT mt.Name FROM tracks t JOIN media_types mt ON t.MediaTypeId = mt.MediaTypeId WHERE t.Name = 'Balls to the Wall';",
    },
    {
        "id": "J11",
        "category": "join",
        "question": "Which playlists contain the track \"Balls to the Wall\"?",
        "sql": "SELECT p.Name FROM playlists p JOIN playlist_track pt ON p.PlaylistId = pt.PlaylistId JOIN tracks t ON pt.TrackId = t.TrackId WHERE t.Name = 'Balls to the Wall';",
    },
    {
        "id": "J12",
        "category": "join",
        "question": "What albums has the artist \"Iron Maiden\" released?",
        "sql": "SELECT a.Title FROM albums a JOIN artists ar ON a.ArtistId = ar.ArtistId WHERE ar.Name = 'Iron Maiden';",
    },
    # --- aggregations / group-bys (8) ---
    {
        "id": "A1",
        "category": "aggregation",
        "question": "Which artist has the most albums?",
        "sql": "SELECT ar.Name FROM albums a JOIN artists ar ON a.ArtistId = ar.ArtistId GROUP BY ar.Name ORDER BY COUNT(*) DESC LIMIT 1;",
    },
    {
        "id": "A2",
        "category": "aggregation",
        "question": "Which genre has the most tracks?",
        "sql": "SELECT g.Name FROM tracks t JOIN genres g ON t.GenreId = g.GenreId GROUP BY g.Name ORDER BY COUNT(*) DESC LIMIT 1;",
    },
    {
        "id": "A3",
        "category": "aggregation",
        "question": "How many tracks are in the playlist named \"Classical\"?",
        "sql": "SELECT COUNT(*) FROM playlists p JOIN playlist_track pt ON p.PlaylistId = pt.PlaylistId WHERE p.Name = 'Classical';",
    },
    {
        "id": "A4",
        "category": "aggregation",
        "question": "Which employee supports the most customers?",
        "sql": "SELECT e.FirstName, e.LastName FROM customers c JOIN employees e ON c.SupportRepId = e.EmployeeId GROUP BY e.EmployeeId ORDER BY COUNT(*) DESC LIMIT 1;",
    },
    {
        "id": "A5",
        "category": "aggregation",
        "question": "What is the total revenue generated by the artist \"Iron Maiden\"?",
        "sql": (
            "SELECT SUM(ii.UnitPrice * ii.Quantity) FROM invoice_items ii "
            "JOIN tracks t ON ii.TrackId = t.TrackId "
            "JOIN albums a ON t.AlbumId = a.AlbumId "
            "JOIN artists ar ON a.ArtistId = ar.ArtistId "
            "WHERE ar.Name = 'Iron Maiden';"
        ),
    },
    {
        "id": "A6",
        "category": "aggregation",
        "question": "Which customer has spent the most money in total?",
        "sql": (
            "SELECT c.FirstName, c.LastName FROM invoices i "
            "JOIN customers c ON i.CustomerId = c.CustomerId "
            "GROUP BY c.CustomerId ORDER BY SUM(i.Total) DESC LIMIT 1;"
        ),
    },
    {
        "id": "A7",
        "category": "aggregation",
        "question": "How many invoices were billed to customers in the USA?",
        "sql": "SELECT COUNT(*) FROM invoices WHERE BillingCountry = 'USA';",
    },
    {
        "id": "A8",
        "category": "aggregation",
        "question": "What is the average length of a track, in milliseconds?",
        "sql": "SELECT AVG(Milliseconds) FROM tracks;",
    },
]
