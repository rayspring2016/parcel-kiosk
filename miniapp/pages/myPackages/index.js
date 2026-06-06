const API = getApp().globalData.API

Page({
  data: {
    packages: [],
    loading: true,
    userId: ""
  },

  async onLoad() {
    // 钉钉小程序通过 dd.getAuthCode + 后端换取 userId
    // 开发阶段从 Storage 读取（正式上线时替换为 dd.getAuthCode）
    const { data: userId } = dd.getStorageSync({ key: "userId" })
    this.setData({ userId: userId || "" })
    await this.fetchPackages()
  },

  onShow() {
    // 从取件确认页返回时刷新列表
    this.fetchPackages()
  },

  async fetchPackages() {
    this.setData({ loading: true })
    try {
      const res = await dd.httpRequest({
        url: `${API}/my-packages?employee_id=${this.data.userId}`,
        method: "GET"
      })
      this.setData({ packages: res.data, loading: false })
    } catch (e) {
      dd.alert({ title: "加载失败", content: e.message || "请检查网络" })
      this.setData({ loading: false })
    }
  },

  async onPickup(e) {
    const code = e.currentTarget.dataset.code
    try {
      await dd.httpRequest({
        url: `${API}/pickup/${code}/confirm`,
        method: "GET"
      })
      dd.showToast({ content: "取件确认成功", type: "success" })
      await this.fetchPackages()
    } catch (e) {
      dd.alert({ title: "操作失败", content: e.message || "请重试" })
    }
  }
})
