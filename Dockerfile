# ===== 1단계: 빌드 =====
FROM eclipse-temurin:25-jdk AS build
WORKDIR /workspace

# 의존성 먼저 받아두면 소스만 바뀌었을 때 빌드가 훨씬 빨라집니다.
COPY gradlew settings.gradle build.gradle ./
COPY gradle gradle
RUN chmod +x gradlew && ./gradlew dependencies --no-daemon || true

COPY src src
RUN ./gradlew clean bootJar --no-daemon -x test

# ===== 2단계: 실행 =====
FROM eclipse-temurin:25-jre
WORKDIR /app

ENV TZ=Asia/Seoul

# root로 돌리지 않기 위한 전용 사용자
RUN groupadd -r spring && useradd -r -g spring spring

COPY --from=build /workspace/build/libs/*.jar app.jar
RUN mkdir -p /app/uploads && chown -R spring:spring /app

USER spring
EXPOSE 8080

# 컨테이너에 할당된 메모리의 75%까지만 JVM이 사용하도록 제한
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/app.jar"]
