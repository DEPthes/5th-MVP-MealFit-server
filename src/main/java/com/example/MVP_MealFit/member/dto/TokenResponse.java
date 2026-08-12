package com.example.MVP_MealFit.member.dto;

public class TokenResponse {

    private final String accessToken;
    private final Long memberId;
    private final String nickname;

    public TokenResponse(String accessToken, Long memberId, String nickname) {
        this.accessToken = accessToken;
        this.memberId = memberId;
        this.nickname = nickname;
    }

    public String getAccessToken() { return accessToken; }
    public Long getMemberId() { return memberId; }
    public String getNickname() { return nickname; }
}