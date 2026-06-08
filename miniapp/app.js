// API 地址集中在 globalData，两个页面不重复定义，修改一处即全局生效
App({
  globalData: {
    API: "http://192.168.3.100:8000",
    userId: ""
  },

  async onLaunch() {
    await this.login()
  },

  async login() {
    try {
      // Step 1: 获取钉钉免登授权码
      const { code } = await new Promise((resolve, reject) =>
        dd.getAuthCode({
          scopes: ["corpid"],
          success: resolve,
          fail: reject
        })
      )
      // Step 2: 用 code 换 userId（后端 /auth/dingtalk 接口）
      const res = await new Promise((resolve, reject) =>
        dd.httpRequest({
          url: `${this.globalData.API}/auth/dingtalk?code=${code}`,
          method: "GET",
          success: resolve,
          fail: reject
        })
      )
      const userId = res.data?.user_id || ""
      this.globalData.userId = userId
      dd.setStorageSync({ key: "userId", data: userId })
    } catch (e) {
      dd.alert({ title: "登录失败", content: "请重启小程序重试" })
    }
  }
})
