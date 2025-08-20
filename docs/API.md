# API Documentation for Multi-Modal Debugging Agent

## Overview
This document provides an overview of the API endpoints available in the Multi-Modal Debugging Agent. Each endpoint is described with its purpose, request parameters, and response format.

## Base URL
The base URL for all API requests is:
```
http://localhost:5000/api
```

## Endpoints

### 1. Get All Models
- **Endpoint:** `/models`
- **Method:** `GET`
- **Description:** Retrieves a list of all data models.
- **Response:**
  - **200 OK**
    - Content: `application/json`
    - Body: 
      ```json
      {
        "models": [
          {
            "id": "1",
            "name": "Model A"
          },
          {
            "id": "2",
            "name": "Model B"
          }
        ]
      }
      ```

### 2. Create a New Model
- **Endpoint:** `/models`
- **Method:** `POST`
- **Description:** Creates a new data model.
- **Request Body:**
  - Content: `application/json`
  - Example:
    ```json
    {
      "name": "Model C"
    }
    ```
- **Response:**
  - **201 Created**
    - Content: `application/json`
    - Body: 
      ```json
      {
        "id": "3",
        "name": "Model C"
      }
      ```

### 3. Get Model by ID
- **Endpoint:** `/models/{id}`
- **Method:** `GET`
- **Description:** Retrieves a specific model by its ID.
- **Parameters:**
  - `id` (path): The ID of the model to retrieve.
- **Response:**
  - **200 OK**
    - Content: `application/json`
    - Body: 
      ```json
      {
        "id": "1",
        "name": "Model A"
      }
      ```
  - **404 Not Found**
    - Content: `application/json`
    - Body: 
      ```json
      {
        "error": "Model not found"
      }
      ```

### 4. Update a Model
- **Endpoint:** `/models/{id}`
- **Method:** `PUT`
- **Description:** Updates an existing model.
- **Parameters:**
  - `id` (path): The ID of the model to update.
- **Request Body:**
  - Content: `application/json`
  - Example:
    ```json
    {
      "name": "Updated Model A"
    }
    ```
- **Response:**
  - **200 OK**
    - Content: `application/json`
    - Body: 
      ```json
      {
        "id": "1",
        "name": "Updated Model A"
      }
      ```

### 5. Delete a Model
- **Endpoint:** `/models/{id}`
- **Method:** `DELETE`
- **Description:** Deletes a specific model by its ID.
- **Parameters:**
  - `id` (path): The ID of the model to delete.
- **Response:**
  - **204 No Content**

## Error Handling
All error responses will include a JSON object with an `error` key describing the issue.

## Conclusion
This API allows for the management of data models within the Multi-Modal Debugging Agent. For further details on specific endpoints or additional functionality, please refer to the source code or contact the development team.