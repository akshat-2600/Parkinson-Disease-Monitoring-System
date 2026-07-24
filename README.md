# 🧠 NeuroTrace – AI-Powered Parkinson's Disease Monitoring System

> An AI-powered healthcare platform for early Parkinson's Disease detection, multi-modal analysis, disease monitoring, and progression tracking using Machine Learning and Deep Learning.

---

## 📌 Overview

NeuroTrace is a full-stack web application that assists in the early detection and continuous monitoring of Parkinson's Disease through multiple diagnostic modalities. Instead of relying on a single test, the system combines predictions from different AI models to provide a comprehensive assessment of a patient's condition.

The platform supports both **Patients** and **Doctors**, offering secure authentication, AI-powered predictions, prediction history, disease progression analysis, explainable AI visualizations, and personalized health recommendations.

---

## ✨ Key Features

### 🔐 Authentication & Authorization
- JWT-based Authentication
- Secure Login & Registration
- Role-Based Access Control (Patient & Doctor)

### 🧠 AI-Based Multi-Modal Prediction
The system supports prediction using multiple independent AI models:

- 🎤 Voice Analysis
- ✍️ Spiral Drawing Analysis
- 🧠 MRI Brain Image Analysis
- 🚶 Motor Assessment
- 📋 Clinical Assessment

### 🔥 Fusion Prediction
Predictions from all modalities are combined using a **Fusion Meta Model** to improve overall accuracy and robustness.

### 📊 Patient Dashboard
- Recent Predictions
- Prediction History
- Confidence Scores
- Disease Risk Level
- Progress Tracking

### 👨‍⚕️ Doctor Dashboard
- View Assigned Patients
- Review Prediction Reports
- Monitor Patient Progress

### 📈 Disease Progression Tracking
- Historical Prediction Records
- Severity Trends
- Progress Timeline

### 🧠 Explainable AI
- Grad-CAM Heatmaps for Image Models
- Visual explanation of CNN predictions

### 💡 Personalized Recommendations
Provides lifestyle and healthcare recommendations based on AI prediction results.

---

# 🏗️ System Architecture



---

# 🛠️ Tech Stack

### Frontend
- React.js
- React Router
- Axios
- Tailwind CSS
- Chart.js

### Backend
- Flask
- Flask REST API
- SQLAlchemy
- JWT Authentication

### Machine Learning
- TensorFlow / Keras
- Scikit-Learn
- OpenCV
- NumPy
- Pandas

### Database
- MySQL

### Tools
- Git
- GitHub
- Postman
- VS Code

---

# 🤖 AI Models

| Modality | Model |
|----------|-------|
| Voice | Support Vector Machine (SVM) |
| Spiral Drawing | EfficientNet-B3 / ResNet50 |
| MRI | EfficientNet-B3 / DenseNet121 / ResNet50 |
| Motor Assessment | Random Forest |
| Clinical Assessment | Random Forest |
| Final Prediction | Fusion Meta Model |

---

<!--

# 📸 Application Screenshots

## 🏠 Home Page

> Replace the image below with your homepage screenshot.

![Home Page](screenshots/home.png)

---

## 🔐 Login Page

![Login](screenshots/login.png)

---

## 📊 Patient Dashboard

![Patient Dashboard](screenshots/patient-dashboard.png)

---

## 👨‍⚕️ Doctor Dashboard

![Doctor Dashboard](screenshots/doctor-dashboard.png)

---

## 🎤 Voice Prediction

![Voice Prediction](screenshots/voice-prediction.png)

---

## 🧠 MRI Prediction

![MRI Prediction](screenshots/mri-prediction.png)

---

## ✍️ Spiral Drawing Prediction

![Spiral Prediction](screenshots/spiral-prediction.png)

---

## 📈 Disease Progress Tracking

![Progress Tracking](screenshots/progress-tracking.png)

---

## 🧠 Explainable AI (Grad-CAM)

![GradCAM](screenshots/gradcam.png)

---

## 💡 Personalized Recommendations

![Recommendations](screenshots/recommendations.png)

---

-->

# 🔮 Future Enhancements

- Wearable Sensor Integration
- Real-Time Voice Recording
- PDF Report Generation
- Cloud Deployment
- Mobile Application
- Telemedicine Support
- Notification & Reminder System

---

# 👨‍💻 Author

**Akshat Saxena**

---

## ⭐ If you found this project useful, consider giving it a star!
